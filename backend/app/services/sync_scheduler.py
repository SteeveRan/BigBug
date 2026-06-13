"""
@file sync_scheduler.py
@description SyncScheduler — APScheduler-based background scheduler for mirror sync
             and freshness checks. Each active SyncGroup gets a scheduled job based on
             its sync_cron and freshness_cron expressions.
@dependencies apscheduler, sqlalchemy, app.services.mirror, app.services.sync_group
@relatedFiles ../services/mirror.py, ../services/sync_group.py, ../services/scheduler.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.sync_group import SyncGroup
from app.models.user import User
from app.services.mirror import MirrorService
from app.services.sync_group import SyncGroupService

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Manages periodic sync and freshness check jobs for all active SyncGroups.

    Jobs are dynamically created/updated/removed when SyncGroup configurations
    change. Uses ``asyncio.Semaphore`` for concurrency control per SyncGroup.

    Each APScheduler job creates its own database session via *session_factory* —
    sessions are NOT shared across jobs or threads.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._sync_jobs: dict[int, str] = {}       # sync_group_id -> job_id
        self._freshness_jobs: dict[int, str] = {}  # sync_group_id -> job_id
        self._semaphores: dict[int, asyncio.Semaphore] = {}
        self._system_user_id: Optional[int] = None   # cached at startup

    # ==================================================================
    # Lifecycle
    # ==================================================================

    async def start(self) -> None:
        """Create and start the AsyncIOScheduler and schedule all active groups."""
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        await self._schedule_all_jobs()
        self._scheduler.start()
        logger.info("SyncScheduler started")

    async def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=True)
            self._scheduler = None
            logger.info("SyncScheduler stopped")

    # ==================================================================
    # Public scheduling interface
    # ==================================================================

    async def schedule_all_jobs(self) -> None:
        """Re-discover active SyncGroups and schedule/update all jobs.

        Call this after SyncGroup config changes (e.g. cron updated,
        enabled/disabled toggled) to keep the scheduler in sync.
        """
        await self._schedule_all_jobs()

    async def schedule_sync_job(
        self,
        sync_group_id: int,
        cron_expr: str,
        concurrency: int,
    ) -> None:
        """Schedule (or re-schedule) the periodic sync job for one SyncGroup.

        Args:
            sync_group_id: The SyncGroup to schedule for.
            cron_expr: Cron expression (e.g. ``"*/30 * * * *"``).
            concurrency: Max concurrent mirror syncs within this group.

        Raises:
            ValueError: If *cron_expr* is not a valid cron expression.
        """
        if self._scheduler is None:
            logger.warning("Cannot schedule sync job: scheduler not started")
            return

        # Validate cron expression early
        trigger = CronTrigger.from_crontab(cron_expr, timezone="UTC")

        self._remove_job_safe(self._sync_jobs.pop(sync_group_id, None))

        job_id = f"sync_group_{sync_group_id}"
        self._scheduler.add_job(
            self._run_sync_for_group,
            trigger=trigger,
            args=[sync_group_id, concurrency],
            id=job_id,
            replace_existing=True,
        )
        self._sync_jobs[sync_group_id] = job_id
        logger.info(
            "Scheduled sync job for SyncGroup %d (cron=%s, concurrency=%d)",
            sync_group_id, cron_expr, concurrency,
        )

    async def schedule_freshness_job(
        self,
        sync_group_id: int,
        cron_expr: str,
        concurrency: int,
    ) -> None:
        """Schedule (or re-schedule) the periodic freshness-check job for one
        SyncGroup.

        Args:
            sync_group_id: The SyncGroup to schedule for.
            cron_expr: Cron expression.
            concurrency: Max concurrent freshness checks within this group.
        """
        if self._scheduler is None:
            logger.warning("Cannot schedule freshness job: scheduler not started")
            return

        self._remove_job_safe(self._freshness_jobs.pop(sync_group_id, None))

        job_id = f"freshness_group_{sync_group_id}"
        trigger = CronTrigger.from_crontab(cron_expr, timezone="UTC")
        self._scheduler.add_job(
            self._run_freshness_for_group,
            trigger=trigger,
            args=[sync_group_id, concurrency],
            id=job_id,
            replace_existing=True,
        )
        self._freshness_jobs[sync_group_id] = job_id
        logger.info(
            "Scheduled freshness job for SyncGroup %d (cron=%s, concurrency=%d)",
            sync_group_id, cron_expr, concurrency,
        )

    def remove_sync_job(self, sync_group_id: int) -> None:
        """Remove the sync job for *sync_group_id* if it exists."""
        job_id = self._sync_jobs.pop(sync_group_id, None)
        self._remove_job_safe(job_id)
        self._semaphores.pop(sync_group_id, None)
        if job_id:
            logger.info("Removed sync job for SyncGroup %d", sync_group_id)

    def remove_freshness_job(self, sync_group_id: int) -> None:
        """Remove the freshness job for *sync_group_id* if it exists."""
        job_id = self._freshness_jobs.pop(sync_group_id, None)
        self._remove_job_safe(job_id)
        if job_id:
            logger.info("Removed freshness job for SyncGroup %d", sync_group_id)

    # ==================================================================
    # Internal scheduling helpers
    # ==================================================================

    async def _schedule_all_jobs(self) -> None:
        """Discover all active SyncGroups and schedule/update their jobs."""
        if self._scheduler is None:
            logger.warning("_schedule_all_jobs called before scheduler started")
            return

        async with self._session_factory() as db:
            groups = await SyncGroupService.get_active_sync_groups(db)
            logger.info("Discovered %d active SyncGroup(s)", len(groups))

            for group in groups:
                if group.sync_enabled and group.sync_cron:
                    try:
                        await self.schedule_sync_job(
                            group.id, group.sync_cron, group.sync_concurrency,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to schedule sync job for SyncGroup %d (cron=%r)",
                            group.id, group.sync_cron,
                        )

                if group.freshness_enabled and group.freshness_cron:
                    try:
                        await self.schedule_freshness_job(
                            group.id, group.freshness_cron, group.freshness_concurrency,
                        )
                    except Exception:
                        logger.exception(
                            "Failed to schedule freshness job for SyncGroup %d (cron=%r)",
                            group.id, group.freshness_cron,
                        )

    # ==================================================================
    # Job coroutines (called by APScheduler)
    # ==================================================================

    async def _run_sync_for_group(
        self, sync_group_id: int, concurrency: int,
    ) -> None:
        """APScheduler job: trigger sync for all mirrors in *sync_group_id*.

        Mirrors are processed concurrently up to *concurrency* via an
        ``asyncio.Semaphore``.  Errors on individual mirrors are logged but
        do not prevent other mirrors from being processed.
        """
        logger.info("Sync job started for SyncGroup %d", sync_group_id)

        semaphore = self._get_semaphore(sync_group_id, concurrency)

        async def _sync_one(mirror_id: int) -> None:
            async with semaphore:
                async with self._session_factory() as db:
                    try:
                        user_id = await self._resolve_user_id(db)
                        await MirrorService.trigger_sync(
                            db=db,
                            mirror_id=mirror_id,
                            user_id=user_id,
                            username="scheduler",
                        )
                        logger.info(
                            "Sync triggered for mirror %d (group %d)",
                            mirror_id, sync_group_id,
                        )
                    except Exception:
                        logger.exception(
                            "Sync failed for mirror %d (group %d)",
                            mirror_id, sync_group_id,
                        )

        async with self._session_factory() as db:
            mirrors = await MirrorService.get_mirrors_by_group(db, sync_group_id)

        if not mirrors:
            logger.info("No mirrors found for SyncGroup %d", sync_group_id)
            return

        tasks = [_sync_one(m.id) for m in mirrors]
        await asyncio.gather(*tasks)

        logger.info(
            "Sync job finished for SyncGroup %d (%d mirror(s) processed)",
            sync_group_id, len(mirrors),
        )

    async def _run_freshness_for_group(
        self, sync_group_id: int, concurrency: int,
    ) -> None:
        """APScheduler job: run freshness check for all mirrors in *sync_group_id*.

        Mirrors are processed concurrently up to *concurrency* via an
        ``asyncio.Semaphore``.  Errors on individual mirrors are logged but
        do not prevent other mirrors from being processed.
        """
        logger.info("Freshness job started for SyncGroup %d", sync_group_id)

        semaphore = self._get_semaphore(sync_group_id, concurrency)

        async def _check_one(mirror_id: int) -> None:
            async with semaphore:
                async with self._session_factory() as db:
                    try:
                        await MirrorService.check_freshness(
                            db=db,
                            mirror_id=mirror_id,
                            username="scheduler",
                        )
                        logger.info(
                            "Freshness check done for mirror %d (group %d)",
                            mirror_id, sync_group_id,
                        )
                    except Exception:
                        logger.exception(
                            "Freshness check failed for mirror %d (group %d)",
                            mirror_id, sync_group_id,
                        )

        async with self._session_factory() as db:
            mirrors = await MirrorService.get_mirrors_by_group(db, sync_group_id)

        if not mirrors:
            logger.info("No mirrors found for SyncGroup %d", sync_group_id)
            return

        tasks = [_check_one(m.id) for m in mirrors]
        await asyncio.gather(*tasks)

        logger.info(
            "Freshness job finished for SyncGroup %d (%d mirror(s) processed)",
            sync_group_id, len(mirrors),
        )

    # ==================================================================
    # Helpers
    # ==================================================================

    def _get_semaphore(
        self, sync_group_id: int, concurrency: int,
    ) -> asyncio.Semaphore:
        """Return (or create) a semaphore for *sync_group_id*."""
        if sync_group_id not in self._semaphores:
            self._semaphores[sync_group_id] = asyncio.Semaphore(max(1, concurrency))
        return self._semaphores[sync_group_id]

    async def _resolve_user_id(self, db: AsyncSession) -> int:
        """Resolve a user ID to use for scheduler-triggered operations.

        Looks up a system user or the first active admin user, caching
        the result for subsequent calls.

        Returns:
            A valid user ID, or 1 as a fallback.
        """
        if self._system_user_id is not None:
            return self._system_user_id

        # Try a user named "system" first
        result = await db.execute(
            select(User.id).where(
                User.username == "system",
                User.is_active == True,
            )
        )
        user_id = result.scalar_one_or_none()
        if user_id is not None:
            self._system_user_id = user_id
            return user_id

        # Fall back to the first active user
        result = await db.execute(
            select(User.id).where(User.is_active == True).order_by(User.id.asc()).limit(1)
        )
        user_id = result.scalar_one_or_none()
        if user_id is not None:
            self._system_user_id = user_id
            return user_id

        # Ultimate fallback — no users in DB (e.g. fresh install)
        logger.warning("No active users found; using user_id=1 as fallback")
        self._system_user_id = 1
        return 1

    def _remove_job_safe(self, job_id: Optional[str]) -> None:
        """Remove an APScheduler job if it exists, catching any errors."""
        if job_id is None or self._scheduler is None:
            return
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass
