"""
@file release.py
@description ReleaseService — tracks releases, collects license info,
             and fetches README content via GitHub API.
@dependencies sqlalchemy, app.core.exceptions, app.services.audit,
             app.services.source_providers.github
@relatedFiles ../models/source_repository.py, ../models/mirror_release_log.py,
             ../services/audit.py
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Optional

from github import GithubException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainException, NotFoundError
from app.models.mirror_release_log import MirrorReleaseLog
from app.models.source_repository import SourceRepository
from app.services.audit import AuditService

if TYPE_CHECKING:
    from app.services.source_providers.github import GitHubSourceProvider

logger = logging.getLogger(__name__)


class ReleaseService:
    """
    Service for tracking releases, collecting license information,
    and fetching README content from source repositories via GitHub API.
    """

    # ------------------------------------------------------------------
    # Release tracking
    # ------------------------------------------------------------------

    @staticmethod
    async def check_new_releases(
        db: AsyncSession,
        source_repository: SourceRepository,
        github_provider: "GitHubSourceProvider",
    ) -> Optional[MirrorReleaseLog]:
        """
        Check for new releases on the source repository via GitHub API.

        Compares the latest release tag from GitHub with the cached tag
        in ``source_repository``. If a new release is detected, updates
        the source repository fields and creates a
        :class:`MirrorReleaseLog` record.

        Args:
            db: Active database session.
            source_repository: The :class:`SourceRepository` ORM object.
            github_provider: Configured :class:`GitHubSourceProvider`.

        Returns:
            The new :class:`MirrorReleaseLog` if a release was detected,
            ``None`` if the latest tag is unchanged or no releases exist.

        Raises:
            DomainException: On GitHub API errors (mapped from GithubException).
        """
        from app.services.source_providers.github import _map_github_exception

        try:
            gh = github_provider._get_client()
            repo = gh.get_repo(source_repository.full_name)

            releases = repo.get_releases()
            if releases.totalCount == 0:
                logger.debug(
                    "No releases found for '%s'", source_repository.full_name
                )
                return None

            # First page, first item = latest release
            latest = releases[0]
            new_tag = latest.tag_name
            current_tag = source_repository.latest_release_tag

            if new_tag == current_tag:
                logger.debug(
                    "No new release for '%s' (current=%s, latest=%s)",
                    source_repository.full_name,
                    current_tag,
                    new_tag,
                )
                return None

            logger.info(
                "New release detected for '%s': %s → %s",
                source_repository.full_name,
                current_tag,
                new_tag,
            )

            # Update SourceRepository
            source_repository.latest_release_tag = new_tag
            source_repository.latest_release_name = latest.title
            source_repository.latest_release_date = latest.published_at
            source_repository.latest_release_url = latest.html_url

            # Create MirrorReleaseLog
            release_log = MirrorReleaseLog(
                source_repository_id=source_repository.id,
                tag=new_tag,
                name=latest.title,
                description=latest.body,
                url=latest.html_url,
                published_at=latest.published_at,
                is_prerelease=latest.prerelease,
            )
            db.add(release_log)
            await db.flush()

            # Audit event (commits the session internally)
            await AuditService.log_event(
                db,
                user_id=None,
                username="system",
                action="mirror.release_detected",
                resource_type="source_repository",
                resource_id=source_repository.id,
                resource_name=source_repository.full_name,
                details={
                    "tag": new_tag,
                    "name": latest.title,
                    "is_prerelease": latest.prerelease,
                    "html_url": latest.html_url,
                },
            )

            return release_log

        except GithubException as exc:
            raise _map_github_exception(
                exc, f"check_new_releases/{source_repository.full_name}"
            ) from exc

    # ------------------------------------------------------------------
    # Release history
    # ------------------------------------------------------------------

    @staticmethod
    async def get_releases(
        db: AsyncSession,
        repository_id: int,
        include_prereleases: bool = False,
        limit: int = 20,
        offset: int = 0,
    ) -> list[MirrorReleaseLog]:
        """
        Get release history for a source repository from the database.

        Args:
            db: Active database session.
            repository_id: The :class:`SourceRepository` id to filter by.
            include_prereleases: When ``True``, include pre-release entries.
                Defaults to ``False``.
            limit: Maximum number of records to return (default 20).
            offset: Pagination offset (default 0).

        Returns:
            List of :class:`MirrorReleaseLog` records ordered by
            ``published_at`` descending.
        """
        stmt = select(MirrorReleaseLog).where(
            MirrorReleaseLog.source_repository_id == repository_id
        )

        if not include_prereleases:
            stmt = stmt.where(MirrorReleaseLog.is_prerelease == False)

        stmt = (
            stmt.order_by(desc(MirrorReleaseLog.published_at))
            .offset(offset)
            .limit(limit)
        )

        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # README
    # ------------------------------------------------------------------

    @staticmethod
    async def fetch_readme_from_source(
        db: AsyncSession,
        source_repository: SourceRepository,
        github_provider: "GitHubSourceProvider",
    ) -> str:
        """
        Fetch README content from GitHub and cache it in the database.

        Retrieves the default-branch README via the GitHub API, decodes
        the base64 content, stores the markdown text in
        ``source_repository.readme_html``, and updates
        ``readme_fetched_at``.

        Args:
            db: Active database session.
            source_repository: The :class:`SourceRepository` to fetch for.
            github_provider: Configured :class:`GitHubSourceProvider`.

        Returns:
            The raw README markdown content as a string.

        Raises:
            DomainException: On GitHub API errors or if the content cannot
                be decoded.
        """
        from app.services.source_providers.github import _map_github_exception

        try:
            gh = github_provider._get_client()
            repo = gh.get_repo(source_repository.full_name)
            readme = repo.get_readme()

            # decoded_content is bytes (UTF-8)
            content = readme.decoded_content.decode("utf-8")

            source_repository.readme_html = content
            source_repository.readme_fetched_at = datetime.now(UTC)

            await db.commit()

            logger.info(
                "README fetched for '%s' (%d chars)",
                source_repository.full_name,
                len(content),
            )
            return content

        except GithubException as exc:
            raise _map_github_exception(
                exc, f"fetch_readme/{source_repository.full_name}"
            ) from exc
        except UnicodeDecodeError as exc:
            raise DomainException(
                f"Failed to decode README for "
                f"'{source_repository.full_name}': {exc}",
                status_code=422,
            ) from exc

    # ------------------------------------------------------------------
    # License
    # ------------------------------------------------------------------

    @staticmethod
    async def fetch_license_from_source(
        db: AsyncSession,
        source_repository: SourceRepository,
        github_provider: "GitHubSourceProvider",
    ) -> dict[str, Any]:
        """
        Fetch license information from GitHub and cache it.

        Retrieves the license via the GitHub API, stores the SPDX
        identifier and human-readable name in ``source_repository``,
        and determines whether the license is restricted.

        Args:
            db: Active database session.
            source_repository: The :class:`SourceRepository` to fetch for.
            github_provider: Configured :class:`GitHubSourceProvider`.

        Returns:
            Dict with keys:

            * ``spdx`` — SPDX license identifier (e.g. ``"MIT"``)
            * ``name`` — Human-readable license name
            * ``is_restricted`` — ``True`` if the license is in the
              restricted list

        Raises:
            DomainException: On GitHub API errors or if no license is found.
        """
        from app.services.source_providers.github import _map_github_exception

        try:
            gh = github_provider._get_client()
            repo = gh.get_repo(source_repository.full_name)
            license_info = repo.get_license()

            spdx = license_info.license.spdx_id
            name = license_info.license.name

            source_repository.license_spdx = spdx
            source_repository.license_name = name

            is_restricted = ReleaseService.check_restricted_license(spdx)

            await db.commit()

            logger.info(
                "License fetched for '%s': %s (%s)%s",
                source_repository.full_name,
                spdx,
                name,
                " [RESTRICTED]" if is_restricted else "",
            )

            return {"spdx": spdx, "name": name, "is_restricted": is_restricted}

        except GithubException as exc:
            raise _map_github_exception(
                exc, f"fetch_license/{source_repository.full_name}"
            ) from exc

    # ------------------------------------------------------------------
    # Restricted license check
    # ------------------------------------------------------------------

    @staticmethod
    def check_restricted_license(license_spdx: str) -> bool:
        """
        Check whether an SPDX license identifier is in the restricted list.

        The restricted list is read from the ``RESTRICTED_LICENSES``
        environment variable, which holds a comma-separated list of
        SPDX codes (e.g. ``"GPL-3.0,AGPL-3.0"``).  Matching is
        case-insensitive.

        Args:
            license_spdx: SPDX identifier (e.g. ``"MIT"``, ``"GPL-3.0"``).

        Returns:
            ``True`` if the license is restricted, ``False`` otherwise.
        """
        restricted_env = os.getenv("RESTRICTED_LICENSES", "")
        if not restricted_env or not license_spdx:
            return False

        restricted_set = {
            lic.strip().upper()
            for lic in restricted_env.split(",")
            if lic.strip()
        }
        return license_spdx.strip().upper() in restricted_set

    # ------------------------------------------------------------------
    # Cached README
    # ------------------------------------------------------------------

    @staticmethod
    async def get_readme(
        db: AsyncSession, repository_id: int
    ) -> Optional[dict[str, Any]]:
        """
        Retrieve cached README content for a source repository.

        Args:
            db: Active database session.
            repository_id: The :class:`SourceRepository` id.

        Returns:
            Dict with keys ``html`` and ``fetched_at`` if README is
            cached, or ``None`` if ``readme_html`` is ``NULL``.

        Raises:
            NotFoundError: If the repository does not exist.
        """
        result = await db.execute(
            select(SourceRepository).where(SourceRepository.id == repository_id)
        )
        repo = result.scalar_one_or_none()

        if repo is None:
            raise NotFoundError(
                f"SourceRepository with id={repository_id} not found"
            )

        if repo.readme_html is None:
            return None

        return {"html": repo.readme_html, "fetched_at": repo.readme_fetched_at}

    # ------------------------------------------------------------------
    # License report
    # ------------------------------------------------------------------

    @staticmethod
    async def get_license_report(
        db: AsyncSession,
        source_group_id: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Generate an aggregated license report across source repositories.

        Groups repositories by ``license_spdx`` and returns per-license
        counts, restriction status, and the list of repositories using
        each license.

        Args:
            db: Active database session.
            source_group_id: Optional filter — only include repositories
                belonging to this :class:`SourceGroup`.

        Returns:
            List of dicts, each with keys:

            * ``spdx`` — SPDX identifier
            * ``name`` — Human-readable license name
            * ``count`` — Number of repositories with this license
            * ``is_restricted`` — Whether the license is restricted
            * ``repositories`` — List of ``{"id", "full_name", "web_url"}``
              dicts for repositories using this license

            Results are sorted alphabetically by license name.
        """
        stmt = select(SourceRepository).where(
            SourceRepository.is_deleted == False,
            SourceRepository.license_spdx.isnot(None),
        )

        if source_group_id is not None:
            stmt = stmt.where(
                SourceRepository.source_group_id == source_group_id
            )

        result = await db.execute(stmt)
        repos = result.scalars().all()

        # Group by license_spdx
        grouped: dict[str, dict[str, Any]] = {}
        for repo in repos:
            spdx: str = repo.license_spdx  # type: ignore[assignment]
            if spdx not in grouped:
                grouped[spdx] = {
                    "spdx": spdx,
                    "name": repo.license_name,
                    "count": 0,
                    "is_restricted": ReleaseService.check_restricted_license(
                        spdx
                    ),
                    "repositories": [],
                }
            grouped[spdx]["count"] += 1
            grouped[spdx]["repositories"].append(
                {
                    "id": repo.id,
                    "full_name": repo.full_name,
                    "web_url": repo.web_url,
                }
            )

        # Sort by license name for stable output
        return sorted(grouped.values(), key=lambda x: x.get("name") or "")
