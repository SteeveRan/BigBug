import re
from datetime import UTC, datetime

from github import Github, GithubException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ExternalServiceError
from app.models.github_org import GithubOrg
from app.models.github_project import GithubProject
from app.models.github_release import GithubRelease


def _parse_github_url(url: str) -> tuple[str, str]:
    """Parse GitHub URL and return (owner, repo) tuple."""
    patterns = [
        r"github\.com[:/]([^/]+)/([^/\.]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), match.group(2)
    raise BadRequestError(f"Cannot parse GitHub URL: {url}")


class GitHubService:
    def _get_client(self) -> Github:
        if not settings.github_token:
            return Github()
        return Github(settings.github_token)

    async def import_project_from_url(self, github_url: str, db: AsyncSession) -> GithubProject:
        owner, repo_name = _parse_github_url(github_url)

        try:
            gh = self._get_client()
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
        await self._sync_releases(gh_repo, project, db)

        await db.commit()
        await db.refresh(project)
        return project

    async def refresh_project(self, project: GithubProject, db: AsyncSession) -> None:
        """Re-fetch metadata from GitHub for an existing project."""
        owner, repo_name = project.full_name.split("/", 1)
        try:
            gh = self._get_client()
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

        await self._sync_releases(gh_repo, project, db)
        await db.commit()

    async def _sync_releases(self, gh_repo, project: GithubProject, db: AsyncSession) -> None:
        """Sync GitHub releases to DB."""
        try:
            releases = gh_repo.get_releases()
            for gh_release in releases:
                rel_result = await db.execute(
                    select(GithubRelease).where(GithubRelease.github_release_id == gh_release.id)
                )
                release = rel_result.scalar_one_or_none()
                if not release:
                    release = GithubRelease(
                        project_id=project.id,
                        github_release_id=gh_release.id,
                    )
                    db.add(release)

                release.tag_name = gh_release.tag_name
                release.name = gh_release.title
                release.body = gh_release.body
                release.is_prerelease = gh_release.prerelease
                release.is_draft = gh_release.draft
                release.published_at = gh_release.published_at
        except GithubException:
            pass


github_service = GitHubService()
