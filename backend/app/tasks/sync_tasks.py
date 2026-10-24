"""Taskiq task bodies for scheduled sync/build/cleanup passes.

APScheduler jobs (app/services/scheduler.py, app/services/sync_scheduler.py)
are enqueue-only: each job takes the job-pass Redis lock and publishes exactly
one of these tasks. Business logic delegates to the existing services
(docker_service, build_service, MirrorService, CleanupService) — unchanged.

Concurrency note: the per-group ``asyncio.Semaphore`` is recreated in the task
body, so it is per-worker — a behavioral change from the previous per-process
semaphore in SyncScheduler. Acceptable at current scale (few workers);
upgrade to a Redis-based semaphore when worker count grows.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.mirror import MirrorService
from app.tasks.broker import broker

logger = logging.getLogger(__name__)

_TASK_LABELS = {
    "max_retries": settings.task_max_retries,
    "ack_type": settings.task_ack_type,
}


async def _resolve_user_id(db: AsyncSession) -> int:
    """Resolve a user for scheduler-triggered operations: "system" user,
    then the first active user, then 1 (fresh install)."""
    result = await db.execute(select(User.id).where(User.username == "system", User.is_active))
    user_id = result.scalar_one_or_none()
    if user_id is not None:
        return user_id

    result = await db.execute(
        select(User.id).where(User.is_active).order_by(User.id.asc()).limit(1)
    )
    user_id = result.scalar_one_or_none()
    if user_id is not None:
        return user_id

    logger.warning("No active users found; using user_id=1 as fallback")
    return 1


async def _run_group_pass(
    group_id: int,
    concurrency: int,
    op: Callable[[AsyncSession, int], Awaitable[object]],
) -> None:
    """Run *op* for every mirror of a SyncGroup, up to *concurrency* in parallel
    (per-worker semaphore). Errors on individual mirrors are logged but do not
    prevent other mirrors from being processed."""
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _one(mirror_id: int) -> None:
        async with semaphore, AsyncSessionLocal() as db:
            try:
                await op(db, mirror_id)
            except Exception:
                logger.exception("Group pass failed for mirror %d (group %d)", mirror_id, group_id)

    async with AsyncSessionLocal() as db:
        mirrors = await MirrorService.get_mirrors_by_group(db, group_id)

    if not mirrors:
        logger.info("No mirrors found for SyncGroup %d", group_id)
        return

    await asyncio.gather(*(_one(m.id) for m in mirrors))
    logger.info("Group pass finished for SyncGroup %d (%d mirror(s))", group_id, len(mirrors))


@broker.task(**_TASK_LABELS)
async def sync_all_task() -> None:
    """Run all enabled docker-image sync schedules."""
    from app.models.docker_image_source import DockerImageSource
    from app.models.docker_image_tag import DockerImageTag
    from app.models.sync_schedule import SyncSchedule
    from app.services.docker import docker_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SyncSchedule).where(SyncSchedule.is_enabled.is_(True)))
        schedules = result.scalars().all()

        for schedule in schedules:
            now = datetime.now(UTC)

            # Determine effective cron
            if schedule.use_default_schedule:
                _ = settings.default_sync_cron
            elif not schedule.cron_expression:
                continue

            # Check if it's time to run
            if schedule.next_run_at and schedule.next_run_at > now:
                continue

            try:
                if schedule.sync_type == "docker_image" and schedule.docker_image_source_id:
                    source_result = await db.execute(
                        select(DockerImageSource).where(
                            DockerImageSource.id == schedule.docker_image_source_id
                        )
                    )
                    source = source_result.scalar_one_or_none()
                    if source and source.target_registry_url:
                        # Sync mode: copy unsynced tags to target registry
                        tags_result = await db.execute(
                            select(DockerImageTag).where(
                                DockerImageTag.source_id == source.id,
                                DockerImageTag.is_synced.is_(False),
                            )
                        )
                        tags = tags_result.scalars().all()

                        for tag in tags:
                            try:
                                await docker_service.sync_image(
                                    source=source,
                                    image_name=tag.image_name,
                                    tag=tag.tag,
                                    db=db,
                                    triggered_by="scheduler",
                                )
                            except Exception as e:
                                logger.error(f"Failed to sync {tag.image_name}:{tag.tag}: {e}")

                        logger.info(f"Synced {len(tags)} tag(s) for docker source {source.id}")
                    elif source:
                        # No target configured: refresh (re-index) tags
                        # Get distinct image names from existing tags
                        names_result = await db.execute(
                            select(DockerImageTag.image_name)
                            .distinct()
                            .where(DockerImageTag.source_id == source.id)
                        )
                        image_names = names_result.scalars().all()
                        for image_name in image_names:
                            try:
                                await docker_service.refresh_source(source, image_name, db)
                                logger.info(f"Refreshed docker source {source.id} for {image_name}")
                            except Exception as e:
                                logger.error(
                                    f"Failed to refresh docker source {source.id}"
                                    f" for {image_name}: {e}"
                                )

                elif schedule.sync_type == "helm_chart" and schedule.helm_chart_source_id:
                    # Helm chart sync — to be implemented
                    logger.info(f"Helm chart sync not yet implemented for schedule {schedule.id}")
                    continue

                schedule.last_run_at = now
            except Exception as e:
                logger.error(f"Failed to trigger sync for schedule {schedule.id}: {e}")

        await db.commit()


@broker.task(**_TASK_LABELS)
async def build_all_task() -> None:
    """Trigger builds for all enabled build schedules."""
    from app.models.app_image import AppImage
    from app.models.build_schedule import BuildSchedule
    from app.models.gold_image import GoldImage
    from app.services.build import build_service

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(BuildSchedule).where(BuildSchedule.is_enabled.is_(True)))
        schedules = result.scalars().all()

        for schedule in schedules:
            now = datetime.now(UTC)

            if schedule.next_run_at and schedule.next_run_at > now:
                continue

            try:
                if schedule.image_type == "gold" and schedule.gold_image_id:
                    img_result = await db.execute(
                        select(GoldImage).where(GoldImage.id == schedule.gold_image_id)
                    )
                    image = img_result.scalar_one_or_none()
                    if image:
                        await build_service.trigger_gold_build(
                            image, "latest", "amd64", db, triggered_by="scheduler"
                        )
                elif schedule.image_type == "app" and schedule.app_image_id:
                    img_result = await db.execute(
                        select(AppImage).where(AppImage.id == schedule.app_image_id)
                    )
                    image = img_result.scalar_one_or_none()
                    if image:
                        await build_service.trigger_app_build(
                            image, "latest", "amd64", db, triggered_by="scheduler"
                        )

                schedule.last_run_at = now
                logger.info(f"Triggered build for schedule {schedule.id}")
            except Exception as e:
                logger.error(f"Failed to trigger build for schedule {schedule.id}: {e}")

        await db.commit()


@broker.task(**_TASK_LABELS)
async def cleanup_task() -> None:
    """Daily physical deletion of soft-deleted Mirroring entities past retention."""
    from app.services.cleanup import cleanup_job

    await cleanup_job()


@broker.task(**_TASK_LABELS)
async def sync_group_task(group_id: int, concurrency: int = 5) -> None:
    """Sync all mirrors of one SyncGroup (up to *concurrency* in parallel per worker)."""

    async def _sync(db: AsyncSession, mirror_id: int) -> None:
        user_id = await _resolve_user_id(db)
        await MirrorService.trigger_sync(
            db=db,
            mirror_id=mirror_id,
            user_id=user_id,
            username="scheduler",
        )

    await _run_group_pass(group_id, concurrency, _sync)


@broker.task(**_TASK_LABELS)
async def freshness_group_task(group_id: int, concurrency: int = 5) -> None:
    """Run freshness checks for all mirrors of one SyncGroup (per-worker semaphore)."""

    async def _check(db: AsyncSession, mirror_id: int) -> None:
        await MirrorService.check_freshness(
            db=db,
            mirror_id=mirror_id,
            username="scheduler",
        )

    await _run_group_pass(group_id, concurrency, _check)
