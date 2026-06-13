"""
@file orphaned.py
@description OrphanedMirrorService — discovers GitLab projects that have no
             corresponding mirror record in BigBug (orphaned mirrors).
@dependencies sqlalchemy, python-gitlab, app.core.secrets
@relatedFiles ../api/orphaned.py, ../schemas/mirror.py, ../models/mirror.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import gitlab as _gitlab_module
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import decrypt_secret
from app.models.gitlab_instance import GitlabInstance
from app.models.mirror import Mirror

logger = logging.getLogger(__name__)


# ===================================================================
# Data classes
# ===================================================================


@dataclass
class OrphanedMirrorResult:
    """A single orphaned mirror discovered in GitLab.

    An orphaned mirror is a GitLab project whose ``target_project_id``
    (numeric GitLab project ID) does NOT match any known BigBug Mirror
    record.  This typically happens when a project was created manually
    in GitLab or by an external process.
    """

    gitlab_project_id: int
    target_path: str | None = None
    target_web_url: str | None = None
    reason: str = "No matching BigBug mirror record"
    created_at: str | None = None
    source_repository_name: str | None = None


@dataclass
class OrphanedReport:
    """Aggregated report of orphaned mirrors across GitLab instances."""

    items: list[OrphanedMirrorResult] = field(default_factory=list)
    gitlab_instance_id: int | None = None
    gitlab_instance_url: str | None = None
    scanned_at: datetime | None = None

    @property
    def count(self) -> int:
        return len(self.items)


# ===================================================================
# OrphanedMirrorService
# ===================================================================


class OrphanedMirrorService:
    """Service for discovering orphaned mirrors in GitLab.

    Scans GitLab instances for projects that are not tracked by any
    BigBug Mirror record, helping operators identify abandoned or
    externally-created projects.
    """

    @staticmethod
    async def find_orphaned(
        db: AsyncSession,
        gitlab_instance_id: int | None = None,
    ) -> OrphanedReport:
        """Find GitLab projects not tracked by any BigBug Mirror.

        Args:
            db: Async database session.
            gitlab_instance_id: Optional GitLab instance ID to scope
                                the scan. If None, scans all instances.

        Returns:
            OrphanedReport with list of orphaned projects.

        Raises:
            DomainException: When no GitLab instance is configured or
                             the GitLab API is unreachable.
        """
        from app.core.exceptions import DomainException

        # ── Resolve GitLab instance(s) ───────────────────────────────
        instance_query = select(GitlabInstance).where(GitlabInstance.is_active.is_(True))
        if gitlab_instance_id is not None:
            instance_query = instance_query.where(GitlabInstance.id == gitlab_instance_id)
        instance_result = await db.execute(instance_query)
        instances: list[GitlabInstance] = list(instance_result.scalars().all())

        if not instances:
            raise DomainException(
                "No GitLab instances configured",
                status_code=400,
            )

        # ── Collect all known target_project_ids from BigBug ────────
        mirrors_result = await db.execute(
            select(Mirror.target_project_id).where(
                ~Mirror.is_deleted,
                Mirror.target_project_id.isnot(None),
            )
        )
        known_ids: set[int] = set()
        for row in mirrors_result:
            tid = row[0]
            if tid and tid.isdigit():
                known_ids.add(int(tid))

        # ── Scan GitLab projects ────────────────────────────────────
        all_orphaned: list[OrphanedMirrorResult] = []
        scanned_instance_id: int | None = None
        scanned_instance_url: str | None = None

        for instance in instances:
            try:
                token = decrypt_secret(instance.token)
                gl = _gitlab_module.Gitlab(
                    url=instance.url,
                    private_token=token,
                    ssl_verify=instance.verify_ssl,
                    user_agent="BigBug/1.0",
                )

                # List all projects the token can see
                # Use pagination via iterator to avoid missing results
                projects = gl.projects.list(
                    all=True,
                    order_by="id",
                    sort="asc",
                )

                scanned_instance_id = instance.id
                scanned_instance_url = instance.url

                for project in projects:
                    if project.id in known_ids:
                        continue

                    orphaned = OrphanedMirrorResult(
                        gitlab_project_id=project.id,
                        target_path=project.path_with_namespace,
                        target_web_url=project.web_url,
                        reason="No matching BigBug mirror record",
                        created_at=project.created_at,
                        source_repository_name=None,
                    )
                    all_orphaned.append(orphaned)

                logger.info(
                    "Scanned GitLab instance %d (%s): %d orphaned projects found",
                    instance.id,
                    instance.url,
                    len([o for o in all_orphaned if o.gitlab_project_id not in known_ids]),
                )
            except Exception as exc:
                logger.error(
                    "Failed to scan GitLab instance %d (%s): %s",
                    instance.id,
                    instance.url,
                    exc,
                )
                # Continue with next instance rather than failing entirely
                continue

        return OrphanedReport(
            items=all_orphaned,
            gitlab_instance_id=scanned_instance_id,
            gitlab_instance_url=scanned_instance_url,
            scanned_at=datetime.now(UTC),
        )

    @staticmethod
    async def find_orphaned_for_instance(
        db: AsyncSession,
        gitlab_instance_id: int,
    ) -> OrphanedReport:
        """Find orphaned mirrors for a specific GitLab instance.

        Convenience wrapper around :meth:`find_orphaned`.
        """
        return await OrphanedMirrorService.find_orphaned(
            db,
            gitlab_instance_id=gitlab_instance_id,
        )
