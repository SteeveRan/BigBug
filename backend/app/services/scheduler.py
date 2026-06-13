import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.config import settings

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="UTC")

    async def start(self) -> None:
        """Start the scheduler and register jobs."""
        self.scheduler.add_job(
            self._run_sync_jobs,
            CronTrigger.from_crontab(settings.default_sync_cron),
            id="sync_all",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_build_jobs,
            CronTrigger.from_crontab(settings.default_build_cron),
            id="build_all",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Scheduler started")

    async def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    async def _run_sync_jobs(self) -> None:
        """Run all enabled sync schedules (docker_image and helm_chart types)."""
        from app.database import AsyncSessionLocal
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
                            # Mirroring mode: copy unsynced tags to target registry
                            tags_result = await db.execute(
                                select(DockerImageTag).where(
                                    DockerImageTag.source_id == source.id,
                                    DockerImageTag.is_synced.is_(False),
                                )
                            )
                            tags = tags_result.scalars().all()

                            for tag in tags:
                                try:
                                    await docker_service.mirror_image(
                                        source=source,
                                        image_name=tag.image_name,
                                        tag=tag.tag,
                                        db=db,
                                        triggered_by="scheduler",
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Failed to mirror {tag.image_name}:{tag.tag}: {e}"
                                    )

                            logger.info(
                                f"Mirrored {len(tags)} tag(s) for docker source {source.id}"
                            )
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
                                    logger.info(
                                        f"Refreshed docker source {source.id} for {image_name}"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"Failed to refresh docker source {source.id}"
                                        f" for {image_name}: {e}"
                                    )

                    elif schedule.sync_type == "helm_chart" and schedule.helm_chart_source_id:
                        # Helm chart sync — to be implemented
                        logger.info(
                            f"Helm chart sync not yet implemented for schedule {schedule.id}"
                        )
                        continue

                    schedule.last_run_at = now
                except Exception as e:
                    logger.error(f"Failed to trigger sync for schedule {schedule.id}: {e}")

            await db.commit()

    async def _run_build_jobs(self) -> None:
        """Run all enabled build schedules."""
        from app.database import AsyncSessionLocal
        from app.models.app_image import AppImage
        from app.models.build_schedule import BuildSchedule
        from app.models.gold_image import GoldImage
        from app.services.build import build_service

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(BuildSchedule).where(BuildSchedule.is_enabled.is_(True))
            )
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


scheduler_service = SchedulerService()
