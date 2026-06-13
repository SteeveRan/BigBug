"""
@file cleanup.py
@description CleanupService — physical deletion of soft-deleted Mirroring entities
             past the configured retention period. Runs as a daily APScheduler cron job
             and optionally via admin API for manual invocation.
@dependencies sqlalchemy, app.database, app.models, app.services.audit, app.config
@relatedFiles ./audit.py, ../models/mirror.py, ../models/mirror_log.py,
              ../models/sync_group.py, ../models/source_repository.py,
              ../models/source_group.py, ../models/pipeline.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.mirror import Mirror
from app.models.mirror_log import MirrorLog
from app.models.pipeline import Pipeline
from app.models.source_group import SourceGroup
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.services.audit import AuditService

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Counts of physically deleted records per entity type."""

    mirror_logs_deleted: int = 0
    mirrors_deleted: int = 0
    sync_groups_deleted: int = 0
    source_repositories_deleted: int = 0
    source_groups_deleted: int = 0
    pipelines_deleted: int = 0

    @property
    def total_deleted(self) -> int:
        return (
            self.mirror_logs_deleted
            + self.mirrors_deleted
            + self.sync_groups_deleted
            + self.source_repositories_deleted
            + self.source_groups_deleted
            + self.pipelines_deleted
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "mirror_logs_deleted": self.mirror_logs_deleted,
            "mirrors_deleted": self.mirrors_deleted,
            "sync_groups_deleted": self.sync_groups_deleted,
            "source_repositories_deleted": self.source_repositories_deleted,
            "source_groups_deleted": self.source_groups_deleted,
            "pipelines_deleted": self.pipelines_deleted,
            "total_deleted": self.total_deleted,
        }


class CleanupService:
    """Physical deletion of soft-deleted Mirroring entities past retention.

    Deletion order respects foreign-key constraints and cascades safely:
    1. MirrorLog (logs belonging to soft-deleted mirrors)
    2. Mirror (soft-deleted past cutoff)
    3. SyncGroup (soft-deleted past cutoff AND has no active mirrors)
    4. SourceRepository (soft-deleted past cutoff AND has no active mirrors)
    5. SourceGroup (soft-deleted past cutoff AND has no non-deleted repositories)
    6. Pipeline (soft-deleted past cutoff AND has no non-deleted sync groups)
    """

    SOFT_DELETE_RETENTION_DAYS: int = settings.soft_delete_retention_days

    @staticmethod
    async def run_cleanup(db: AsyncSession) -> CleanupResult:
        """Execute one full cleanup pass.

        Returns a ``CleanupResult`` with per-entity deletion counts.  Writes an
        audit event ``cleanup.executed`` regardless of whether any records were
        actually removed.
        """
        cutoff = datetime.now(UTC) - timedelta(days=CleanupService.SOFT_DELETE_RETENTION_DAYS)
        result = CleanupResult()

        # 1. MirrorLogs — delete logs for soft-deleted mirrors past retention
        mirror_logs_query = (
            select(MirrorLog)
            .join(Mirror, MirrorLog.mirror_id == Mirror.id)
            .where(
                Mirror.is_deleted.is_(True),
                Mirror.deleted_at.is_not(None),
                Mirror.deleted_at < cutoff,
            )
            .options(selectinload(MirrorLog.mirror).selectinload(Mirror.mirror_logs))
        )
        mirror_logs_result = await db.execute(mirror_logs_query)
        mirror_logs = mirror_logs_result.scalars().all()
        for log_entry in mirror_logs:
            await db.delete(log_entry)
        result.mirror_logs_deleted = len(mirror_logs)

        await db.flush()

        # 2. Mirrors — soft-deleted past retention
        mirrors_query = (
            select(Mirror)
            .where(
                Mirror.is_deleted.is_(True),
                Mirror.deleted_at.is_not(None),
                Mirror.deleted_at < cutoff,
            )
            .options(selectinload(Mirror.mirror_logs))
        )
        mirrors_result = await db.execute(mirrors_query)
        mirrors = mirrors_result.scalars().all()
        for mirror in mirrors:
            await db.delete(mirror)
        result.mirrors_deleted = len(mirrors)

        await db.flush()

        # 3. SyncGroups — soft-deleted past retention AND no active mirrors
        sync_groups_query = (
            select(SyncGroup)
            .where(
                SyncGroup.is_deleted.is_(True),
                SyncGroup.deleted_at.is_not(None),
                SyncGroup.deleted_at < cutoff,
            )
            .options(selectinload(SyncGroup.mirrors))
        )
        sync_groups_result = await db.execute(sync_groups_query)
        sync_groups = sync_groups_result.scalars().all()
        for sg in sync_groups:
            has_active_mirrors = any(not m.is_deleted for m in sg.mirrors)
            if not has_active_mirrors:
                await db.delete(sg)
                result.sync_groups_deleted += 1

        await db.flush()

        # 4. SourceRepositories — soft-deleted past retention AND no active mirrors
        source_repos_query = (
            select(SourceRepository)
            .where(
                SourceRepository.is_deleted.is_(True),
                SourceRepository.deleted_at.is_not(None),
                SourceRepository.deleted_at < cutoff,
            )
            .options(selectinload(SourceRepository.mirrors))
        )
        source_repos_result = await db.execute(source_repos_query)
        source_repos = source_repos_result.scalars().all()
        for sr in source_repos:
            has_active_mirrors = any(not m.is_deleted for m in sr.mirrors)
            if not has_active_mirrors:
                await db.delete(sr)
                result.source_repositories_deleted += 1

        await db.flush()

        # 5. SourceGroups — soft-deleted past retention AND no non-deleted repositories
        source_groups_query = (
            select(SourceGroup)
            .where(
                SourceGroup.is_deleted.is_(True),
                SourceGroup.deleted_at.is_not(None),
                SourceGroup.deleted_at < cutoff,
            )
            .options(selectinload(SourceGroup.source_repositories))
        )
        source_groups_result = await db.execute(source_groups_query)
        source_groups = source_groups_result.scalars().all()
        for sg_item in source_groups:
            has_active_repos = any(not repo.is_deleted for repo in sg_item.source_repositories)
            if not has_active_repos:
                await db.delete(sg_item)
                result.source_groups_deleted += 1

        await db.flush()

        # 6. Pipelines — soft-deleted past retention AND no non-deleted sync groups
        pipelines_query = (
            select(Pipeline)
            .where(
                Pipeline.is_deleted.is_(True),
                Pipeline.deleted_at.is_not(None),
                Pipeline.deleted_at < cutoff,
            )
            .options(selectinload(Pipeline.sync_groups))
        )
        pipelines_result = await db.execute(pipelines_query)
        pipelines = pipelines_result.scalars().all()
        for pl in pipelines:
            has_active_sync_groups = any(not sg.is_deleted for sg in pl.sync_groups)
            if not has_active_sync_groups:
                await db.delete(pl)
                result.pipelines_deleted += 1

        await db.commit()

        if result.total_deleted > 0:
            logger.info("Cleanup completed: %s", result.to_dict())
        else:
            logger.debug("Cleanup completed: no records deleted")

        # Audit event — system action
        await AuditService.log_event(
            db,
            user_id=None,
            username="system",
            action="cleanup.executed",
            resource_type="cleanup",
            details=result.to_dict(),
        )

        return result


async def cleanup_job() -> None:
    """Thin wrapper for APScheduler — creates its own DB session."""
    from app.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            await CleanupService.run_cleanup(db)
        except Exception:
            logger.exception("Scheduled cleanup job failed")
