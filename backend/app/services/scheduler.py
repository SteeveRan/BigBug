"""SchedulerService — APScheduler is enqueue-only (ADR-0039).

Job bodies take the job-pass Redis lock and publish one taskiq task per pass;
no business logic runs in the API process. Execution happens in the taskiq
worker (app/tasks/sync_tasks.py).
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.tasks.enqueue import enqueue
from app.tasks.pass_lock import job_pass_lock
from app.tasks.reconcile_tasks import reconcile_all_task
from app.tasks.sync_tasks import build_all_task, cleanup_task, sync_all_task

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
        self.scheduler.add_job(
            self._run_cleanup_job,
            CronTrigger(hour=settings.cleanup_cron_hour, minute=0),
            id="cleanup",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._run_reconcile_job,
            CronTrigger.from_crontab(settings.reconcile_cron),
            id="reconcile",
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info("Scheduler started")

    async def stop(self) -> None:
        self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    async def _run_sync_jobs(self) -> None:
        """Enqueue one sync_all pass (lock prevents double-enqueue across replicas)."""
        async with job_pass_lock("sync_all") as acquired:
            if not acquired:
                return
            await enqueue(sync_all_task)

    async def _run_build_jobs(self) -> None:
        """Enqueue one build_all pass."""
        async with job_pass_lock("build_all") as acquired:
            if not acquired:
                return
            await enqueue(build_all_task)

    async def _run_cleanup_job(self) -> None:
        """Enqueue one cleanup pass."""
        async with job_pass_lock("cleanup") as acquired:
            if not acquired:
                return
            await enqueue(cleanup_task)

    async def _run_reconcile_job(self) -> None:
        """Enqueue one reconciliation pass (drift catcher, ADR-0039 Phase 3)."""
        async with job_pass_lock("reconcile") as acquired:
            if not acquired:
                return
            await enqueue(reconcile_all_task)


scheduler_service = SchedulerService()
