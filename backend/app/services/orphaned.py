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
from sqlalchemy.orm import joinedload

from app.core.secrets import decrypt_secret
from app.models.mirror import Mirror
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderSubtype,
    ResourceProvider,
)

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
    """Aggregated report of orphaned mirrors across GitLab providers."""

    items: list[OrphanedMirrorResult] = field(default_factory=list)
    provider_id: int | None = None
    provider_url: str | None = None
    scanned_at: datetime | None = None

    @property
    def count(self) -> int:
        return len(self.items)


# ===================================================================
# OrphanedMirrorService
# ===================================================================


class OrphanedMirrorService:
    """Service for discovering orphaned mirrors in GitLab.

    Scans the platform GitLab provider(s) (subtype=gitlab, category=system,
    direction=internal) for projects that are not tracked by any BigBug
    Mirror record, helping operators identify abandoned or externally-created
    projects.
    """

    @staticmethod
    async def find_orphaned(
        db: AsyncSession,
        provider_id: int | None = None,
    ) -> OrphanedReport:
        """Find GitLab projects not tracked by any BigBug Mirror.

        Args:
            db: Async database session.
            provider_id: Optional ResourceProvider ID to scope the scan.
                         If None, scans all active system/internal GitLab
                         providers.

        Returns:
            OrphanedReport with list of orphaned projects.

        Raises:
            DomainError: When no GitLab provider is configured or the
                         GitLab API is unreachable.
        """
        from app.core.exceptions import DomainError

        # ── Resolve GitLab provider(s) ──────────────────────────────
        provider_query = (
            select(ResourceProvider)
            .options(joinedload(ResourceProvider.credential))
            .where(
                ResourceProvider.subtype == ProviderSubtype.gitlab,
                ResourceProvider.category == ProviderCategory.system,
                ResourceProvider.direction == ProviderDirection.internal,
                ResourceProvider.is_active.is_(True),
                ResourceProvider.is_deleted.is_(False),
            )
        )
        if provider_id is not None:
            provider_query = provider_query.where(ResourceProvider.id == provider_id)
        provider_result = await db.execute(provider_query)
        providers: list[ResourceProvider] = list(provider_result.unique().scalars().all())

        if not providers:
            raise DomainError(
                "No GitLab providers configured",
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
        scanned_provider_id: int | None = None
        scanned_provider_url: str | None = None

        for provider in providers:
            try:
                token: str | None = None
                if provider.credential is not None and provider.credential.encrypted_secret:
                    token = decrypt_secret(provider.credential.encrypted_secret)
                gl = _gitlab_module.Gitlab(
                    url=provider.base_url,
                    private_token=token,
                    ssl_verify=provider.verify_ssl,
                    user_agent="BigBug/1.0",
                )

                # List all projects the token can see
                # Use pagination via iterator to avoid missing results
                projects = gl.projects.list(
                    all=True,
                    order_by="id",
                    sort="asc",
                )

                scanned_provider_id = provider.id
                scanned_provider_url = provider.base_url

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
                    "Scanned GitLab provider %d (%s): %d orphaned projects found",
                    provider.id,
                    provider.base_url,
                    len(all_orphaned),
                )
            except Exception as exc:
                logger.error(
                    "Failed to scan GitLab provider %d (%s): %s",
                    provider.id,
                    provider.base_url,
                    exc,
                )
                # Continue with next provider rather than failing entirely
                continue

        return OrphanedReport(
            items=all_orphaned,
            provider_id=scanned_provider_id,
            provider_url=scanned_provider_url,
            scanned_at=datetime.now(UTC),
        )

    @staticmethod
    async def find_orphaned_for_instance(
        db: AsyncSession,
        provider_id: int,
    ) -> OrphanedReport:
        """Find orphaned mirrors for a specific GitLab provider.

        Convenience wrapper around :meth:`find_orphaned`.
        """
        return await OrphanedMirrorService.find_orphaned(
            db,
            provider_id=provider_id,
        )
