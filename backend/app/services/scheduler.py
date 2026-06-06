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
        """Run all enabled sync schedules."""
        from app.database import AsyncSessionLocal
        from app.models.gitlab_mirror import GitlabMirror
        from app.models.sync_schedule import SyncSchedule
        from app.services.gitlab import gitlab_service

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

                mirror_result = await db.execute(
                    select(GitlabMirror).where(GitlabMirror.id == schedule.mirror_id)
                )
                mirror = mirror_result.scalar_one_or_none()
                if not mirror or not mirror.pipeline_trigger_token:
                    continue

                try:
                    await gitlab_service.trigger_sync(mirror, db, triggered_by="scheduler")
                    schedule.last_run_at = now
                    logger.info(f"Triggered sync for mirror {mirror.id}")
                except Exception as e:
                    logger.error(f"Failed to trigger sync for mirror {mirror.id}: {e}")

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
