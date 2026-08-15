"""
@file github.py
@description GitHub project service — import/repository discovery, metadata
             refresh, and release syncing. Resolves the GitHub client from a
             unified ``ResourceProvider`` (subtype=github, direction=external);
             falls back to the seeded anonymous public provider, then to
             settings.GITHUB_TOKEN for backward compatibility.
@dependencies PyGithub, app.config.settings, app.core.secrets,
               app.models.resource_provider
@relatedFiles ../models/resource_provider.py, ../models/github_project.py,
               ../core/secrets.py
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from github import Github, GithubException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.core.exceptions import BadRequestError, ExternalServiceError
from app.core.secrets import decrypt_secret
from app.models.github_org import GithubOrg
from app.models.github_project import GithubProject
from app.models.github_release import GithubRelease
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderSubtype,
    ResourceProvider,
)


def _parse_github_url(url: str) -> tuple[str, str]:
    """Parse a GitHub URL and return (owner, repo) tuple."""
    patterns = [
        r"github\.com[:/]([^/]+)/([^/\.]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise BadRequestError(f"Cannot parse GitHub URL: {url}")


class GitHubService:
    """Service for interacting with GitHub projects."""

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    @staticmethod
    async def get_default_provider(db: AsyncSession) -> ResourceProvider | None:
        """Return the default GitHub provider from ``resource_providers``.

        Priority:
        1. An active private provider (category=private) with a credential.
        2. An active public provider (category=public) — the seeded
           ``github-anonymous`` row (no credential required).

        The credential relationship is eager-loaded so callers can decrypt the
        token without triggering an async lazy load.
        """
        stmt = (
            select(ResourceProvider)
            .options(joinedload(ResourceProvider.credential))
            .where(
                ResourceProvider.subtype == ProviderSubtype.github,
                ResourceProvider.direction == ProviderDirection.external,
                ResourceProvider.is_active.is_(True),
                ResourceProvider.is_deleted.is_(False),
            )
        )

        # 1. Private provider with a credential (authenticated access).
        private = await db.execute(
            stmt.where(ResourceProvider.category == ProviderCategory.private).limit(1)
        )
        provider = private.unique().scalar_one_or_none()
        if provider is not None and provider.credential_id is not None:
            return provider

        # 2. Public provider (anonymous fallback, e.g. github-anonymous).
        public = await db.execute(
            stmt.where(ResourceProvider.category == ProviderCategory.public)
            .order_by(ResourceProvider.is_default.desc(), ResourceProvider.id.asc())
            .limit(1)
        )
        return public.unique().scalar_one_or_none()

    # ------------------------------------------------------------------
    # Client factory
    # ------------------------------------------------------------------

    def _get_client(self, provider: ResourceProvider | None = None) -> Github:
        """
        Build a PyGithub client.

        Priority:
        1. ``provider`` — use its ``config.api_url`` base URL (if set) and
           *decrypted* credential secret (if present).
        2. ``settings.github_token`` (fallback).
        3. Unauthenticated ``Github()`` if neither is available.
        """
        if provider is not None:
            api_url = (provider.config or {}).get("api_url")
            token: str | None = None
            if provider.credential is not None and provider.credential.encrypted_secret:
                token = decrypt_secret(provider.credential.encrypted_secret)

            kwargs: dict = {}
            if api_url:
                kwargs["base_url"] = api_url
            if token:
                return Github(token, **kwargs)
            return Github(**kwargs)

        # Backward-compatible fallback
        if settings.github_token:
            return Github(settings.github_token)
        return Github()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def import_project_from_url(
        self,
        github_url: str,
        db: AsyncSession,
        *,
        provider: ResourceProvider | None = None,
    ) -> GithubProject:
        """Discover a GitHub repository and persist it as a project."""
        owner, repo_name = _parse_github_url(github_url)

        if provider is None:
            provider = await self.get_default_provider(db)

        try:
            gh = self._get_client(provider)
            gh_repo = gh.get_repo(f"{owner}/{repo_name}")
        except GithubException as e:
            raise ExternalServiceError("GitHub", str(e)) from e

        # Get or create org
        org_result = await db.execute(select(GithubOrg).where(GithubOrg.login == owner))
        org = org_result.scalar_one_or_none()
        if not org:
            try:
                gh_user = gh.get_user(owner)
                org = GithubOrg(
                    login=owner,
                    type=gh_user.type,
                    avatar_url=gh_user.avatar_url,
                    github_id=gh_user.id,
                )
            except GithubException:
                org = GithubOrg(login=owner, type="Organization")
            db.add(org)
            await db.flush()

        # Check if project already exists
        proj_result = await db.execute(
            select(GithubProject).where(GithubProject.full_name == gh_repo.full_name)
        )
        project = proj_result.scalar_one_or_none()

        if not project:
            project = GithubProject(org_id=org.id)
            db.add(project)

        # Update fields from GitHub
        project.github_id = gh_repo.id
        project.name = gh_repo.name
        project.full_name = gh_repo.full_name
        project.github_url = gh_repo.html_url
        project.description = gh_repo.description
        project.default_branch = gh_repo.default_branch or "main"
        project.homepage_url = gh_repo.homepage
        project.is_archived = gh_repo.archived
        project.is_fork = gh_repo.fork
        project.github_created_at = gh_repo.created_at
        project.github_updated_at = gh_repo.updated_at
        project.github_pushed_at = gh_repo.pushed_at

        # License
        if gh_repo.license:
            project.license_spdx = gh_repo.license.spdx_id
            project.license_name = gh_repo.license.name

        # README
        try:
            readme = gh_repo.get_readme()
            project.readme_md = readme.decoded_content.decode("utf-8", errors="replace")
        except GithubException:
            pass

        project.last_synced_at = datetime.now(UTC)

        await db.flush()

        # Sync releases
        # Schedule releases sync as a background task to avoid blocking
        import asyncio

        from app.database import AsyncSessionLocal

        # Create a new session for the background task
        async def sync_releases_background():
            async with AsyncSessionLocal() as new_db:
                try:
                    # Fetch fresh project instance for the background session
                    result = await new_db.execute(
                        select(GithubProject).where(GithubProject.id == project.id)
                    )
                    bg_project = result.scalar_one()

                    # Get fresh repo instance
                    gh = self._get_client(provider)
                    bg_gh_repo = gh.get_repo(project.full_name)

                    # Execute the sync with a timeout to prevent indefinite blocking
                    import asyncio

                    try:
                        await asyncio.wait_for(
                            self._sync_releases(bg_gh_repo, bg_project, new_db),
                            timeout=30.0,  # 30 second timeout for the sync operation
                        )
                    except TimeoutError:
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.error(
                            f"Sync releases timed out for project "
                            f"{project.full_name} after 30 seconds"
                        )

                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Background sync releases failed for project {project.full_name}: {str(e)}"
                    )
                    # Check if this is a GitHub API rate limit error
                    if "rate limit" in str(e).lower() or (
                        "403" in str(e) and "exceeded" in str(e).lower()
                    ):
                        logger.error(
                            "This error may be caused by GitHub API rate limits. "
                            "Please configure a GitHub personal access token "
                            "to increase the rate limit."
                        )

        # Schedule the background task
        asyncio.create_task(sync_releases_background())

        await db.commit()
        await db.refresh(project)
        return project

    async def refresh_project(
        self,
        project: GithubProject,
        db: AsyncSession,
        *,
        provider: ResourceProvider | None = None,
    ) -> None:
        """Re-fetch metadata from GitHub for an existing project."""
        if provider is None:
            provider = await self.get_default_provider(db)

        try:
            gh = self._get_client(provider)
            gh_repo = gh.get_repo(project.full_name)
        except GithubException as e:
            raise ExternalServiceError("GitHub", str(e)) from e

        project.description = gh_repo.description
        project.homepage_url = gh_repo.homepage
        project.is_archived = gh_repo.archived
        project.github_updated_at = gh_repo.updated_at
        project.github_pushed_at = gh_repo.pushed_at
        project.last_synced_at = datetime.now(UTC)

        if gh_repo.license:
            project.license_spdx = gh_repo.license.spdx_id
            project.license_name = gh_repo.license.name

        try:
            readme = gh_repo.get_readme()
            project.readme_md = readme.decoded_content.decode("utf-8", errors="replace")
        except GithubException:
            pass

        # Schedule releases sync as a background task to avoid blocking
        import asyncio

        from app.database import AsyncSessionLocal

        # Create a new session for the background task
        async def sync_releases_background():
            async with AsyncSessionLocal() as new_db:
                try:
                    # Fetch fresh project instance for the background session
                    result = await new_db.execute(
                        select(GithubProject).where(GithubProject.id == project.id)
                    )
                    bg_project = result.scalar_one()

                    # Get fresh repo instance
                    gh = self._get_client(provider)
                    bg_gh_repo = gh.get_repo(project.full_name)

                    # Execute the sync with a timeout to prevent indefinite blocking
                    import asyncio

                    try:
                        await asyncio.wait_for(
                            self._sync_releases(bg_gh_repo, bg_project, new_db),
                            timeout=30.0,  # 30 second timeout for the sync operation
                        )
                    except TimeoutError:
                        import logging

                        logger = logging.getLogger(__name__)
                        logger.error(
                            f"Sync releases timed out for project "
                            f"{project.full_name} after 30 seconds"
                        )

                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(
                        f"Background sync releases failed for project {project.full_name}: {str(e)}"
                    )
                    # Check if this is a GitHub API rate limit error
                    if "rate limit" in str(e).lower() or (
                        "403" in str(e) and "exceeded" in str(e).lower()
                    ):
                        logger.error(
                            "This error may be caused by GitHub API rate limits. "
                            "Please configure a GitHub personal access token "
                            "to increase the rate limit."
                        )

        # Schedule the background task
        asyncio.create_task(sync_releases_background())

        await db.commit()

    async def _sync_releases(self, gh_repo, project: GithubProject, db: AsyncSession) -> None:
        """Sync GitHub releases to DB."""
        import logging

        logger = logging.getLogger(__name__)

        try:
            logger.info(f"Starting to sync releases for project {project.full_name}")

            # Execute GitHub API call with timeout to prevent blocking
            import asyncio

            async def fetch_releases():
                loop = asyncio.get_event_loop()
                # Use run_in_executor to handle potential sync operations that might block
                releases = await loop.run_in_executor(None, gh_repo.get_releases)
                return list(releases)

            # Fetch releases with timeout
            releases_list = await asyncio.wait_for(fetch_releases(), timeout=20.0)
            logger.info(
                f"Found {len(releases_list)} releases from GitHub for project {project.full_name}"
            )

            release_count = 0
            for gh_release in releases_list:
                logger.debug(f"Processing release: {gh_release.tag_name} (ID: {gh_release.id})")

                rel_result = await db.execute(
                    select(GithubRelease).where(GithubRelease.github_release_id == gh_release.id)
                )
                release = rel_result.scalar_one_or_none()

                if not release:
                    logger.debug(f"Creating new release record for {gh_release.tag_name}")
                    release = GithubRelease(
                        project_id=project.id,
                        github_release_id=gh_release.id,
                    )
                    db.add(release)

                # Update release fields
                release.tag_name = gh_release.tag_name
                release.name = gh_release.title
                release.body = gh_release.body
                release.is_prerelease = gh_release.prerelease
                release.is_draft = gh_release.draft
                release.published_at = gh_release.published_at
                release_count += 1

            logger.info(
                f"Successfully synced {release_count} releases for project {project.full_name}"
            )

            # Commit the changes to database
            await db.flush()

        except TimeoutError:
            logger.error(f"Timeout while syncing releases for project {project.full_name}")
        except GithubException as e:
            logger.error(
                f"GitHub API error while syncing releases for "
                f"project {project.full_name}: {str(e)} (Status: {e.status})"
            )
            # Check if this is a rate limit error
            if e.status == 403:
                # Check specifically for rate limit exceeded
                if (
                    "rate limit" in str(e.data).lower()
                    or "api rate limit exceeded" in str(e.data).lower()
                ):
                    logger.error(
                        "GitHub API rate limit exceeded. Please configure a GitHub personal "
                        "access token in the settings or integration instance to increase the "
                        "rate limit."
                    )
                else:
                    logger.error(
                        "Access forbidden (403). This could be due to repository permissions "
                        "or API rate limits. Please check your GitHub token configuration."
                    )
        except Exception as e:
            logger.error(
                f"Unexpected error while syncing releases for "
                f"project {project.full_name}: {str(e)}",
                exc_info=True,
            )


# Module-level singleton (backward-compatible)
github_service = GitHubService()
