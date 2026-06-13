"""
@file source_providers/gitlab.py
@description GitLab concrete implementation of BaseSourceProvider.
             Discovers groups, projects, releases, READMEs and commit
             metadata via the python-gitlab library.  Supports both
             gitlab.com (cloud) and self-hosted GitLab instances.
@dependencies python-gitlab (gitlab.Gitlab, gitlab.exceptions),
            app.core.exceptions.DomainException,
            app.services.source_provider.BaseSourceProvider
@relatedFiles ../source_provider.py, ../../models/source_provider.py,
             ../../models/source_group.py, ../../models/source_repository.py
"""

from __future__ import annotations

import asyncio
import html as _html_module
import logging
from typing import TYPE_CHECKING

import gitlab
from gitlab.exceptions import GitlabAuthenticationError, GitlabError

from app.core.exceptions import DomainException
from app.services.source_provider import BaseSourceProvider

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SPDX license mapping: GitLab license keys/names -> SPDX identifiers
# ---------------------------------------------------------------------------
# GitLab exposes a ``project.license`` dict with keys like "key", "name",
# "nickname".  The ``key`` field (e.g. "mit", "apache-2.0") is often close
# to the SPDX id, but not always.  This mapping covers the most common
# licenses returned by the GitLab API.
# ---------------------------------------------------------------------------

_GITLAB_LICENSE_TO_SPDX: dict[str, str | None] = {
    # SPDX keys (already correct)
    "mit": "MIT",
    "apache-2.0": "Apache-2.0",
    "gpl-2.0": "GPL-2.0-only",
    "gpl-3.0": "GPL-3.0-only",
    "lgpl-2.1": "LGPL-2.1-only",
    "lgpl-3.0": "LGPL-3.0-only",
    "agpl-3.0": "AGPL-3.0-only",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "mpl-2.0": "MPL-2.0",
    "unlicense": "Unlicense",
    "cc0-1.0": "CC0-1.0",
    "epl-2.0": "EPL-2.0",
    "wtfpl": "WTFPL",
    # GitLab-specific keys
    "other": None,
    # Common full-name -> SPDX fallbacks (lowercased for matching)
    "mit license": "MIT",
    "apache license 2.0": "Apache-2.0",
    "apache license version 2.0": "Apache-2.0",
    "gnu general public license v2.0": "GPL-2.0-only",
    "gnu general public license v3.0": "GPL-3.0-only",
    "gnu lesser general public license v2.1": "LGPL-2.1-only",
    "gnu lesser general public license v3.0": "LGPL-3.0-only",
    "gnu affero general public license v3.0": "AGPL-3.0-only",
    "bsd 2-clause simplified license": "BSD-2-Clause",
    "bsd 3-clause new or revised license": "BSD-3-Clause",
    "mozilla public license 2.0": "MPL-2.0",
    "the unlicense": "Unlicense",
    "creative commons zero v1.0 universal": "CC0-1.0",
    "eclipse public license 2.0": "EPL-2.0",
    "do what the f*ck you want to public license": "WTFPL",
}


def _resolve_license_spdx(license_obj: dict | None) -> tuple[str | None, str | None]:
    """
    Resolve a GitLab license dict to a (spdx_id, name) pair.

    Args:
        license_obj: The project.license dict from python-gitlab, or None.

    Returns:
        A (license_spdx, license_name) tuple.  Either element may be
        None if the license cannot be resolved.
    """
    if not license_obj or not isinstance(license_obj, dict):
        return None, None

    # The GitLab API may return the license as a dict with 'key', 'name',
    # 'nickname' keys.  Try several resolution strategies.
    license_key: str | None = license_obj.get("key")
    license_name: str | None = license_obj.get("name")

    # 1. Try mapping by key (lowercased)
    spdx: str | None = None
    if license_key:
        spdx = _GITLAB_LICENSE_TO_SPDX.get(license_key.lower())

    # 2. If key mapping failed, try the full name
    if spdx is None and license_name:
        spdx = _GITLAB_LICENSE_TO_SPDX.get(license_name.lower())

    # 3. If still no SPDX found but we have a key that looks valid, use it
    if (
        spdx is None
        and license_key
        and license_key.lower() not in ("other", "none", "no license", "")
    ):
        spdx = license_key.upper()

    return spdx, license_name


# ---------------------------------------------------------------------------
# Exception mapping
# ---------------------------------------------------------------------------


def _map_gitlab_exception(exc: GitlabError, operation: str) -> DomainException:
    """
    Map a GitlabError to a DomainException with an appropriate HTTP status
    code and human-readable message.

    Args:
        exc: The original GitLab exception.
        operation: Human-readable description of the failed operation
                   (e.g. "list_groups", "get_repository/foo/bar").

    Returns:
        A DomainException with a mapped HTTP status code.
    """
    # python-gitlab error responses typically have a numeric response_code
    status = getattr(exc, "response_code", 0)

    message = str(exc)

    if isinstance(exc, GitlabAuthenticationError) or status == 401:
        return DomainException(
            f"GitLab authentication failed during {operation}: {message}",
            status_code=401,
        )
    if status == 403:
        return DomainException(
            f"GitLab access forbidden during {operation}: {message}",
            status_code=403,
        )
    if status == 404:
        return DomainException(
            f"GitLab resource not found during {operation}: {message}",
            status_code=404,
        )
    if status == 422:
        return DomainException(
            f"GitLab validation failed during {operation}: {message}",
            status_code=422,
        )
    if status == 429:
        return DomainException(
            f"GitLab rate limit exceeded during {operation}: {message}",
            status_code=429,
        )

    # Generic fallback -- treat as bad gateway
    return DomainException(
        f"GitLab API error during {operation} (status={status}): {message}",
        status_code=502,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _group_to_dict(group) -> dict:
    """
    Convert a python-gitlab Group object to a flat dict.

    Args:
        group: A gitlab.v4.objects.groups.Group instance.

    Returns:
        Dict with group metadata matching the BaseSourceProvider contract.
    """
    return {
        "external_id": group.id,
        "name": group.name,
        "full_name": group.full_name or group.name,
        "full_path": group.full_path,
        "description": getattr(group, "description", None) or "",
        "web_url": group.web_url,
        "avatar_url": getattr(group, "avatar_url", None),
        "parent_id": getattr(group, "parent_id", None),
    }


def _project_to_dict(project) -> dict:
    """
    Convert a python-gitlab Project object to a flat dict.

    Args:
        project: A gitlab.v4.objects.projects.Project instance.

    Returns:
        Dict with repository metadata.
    """
    return {
        "external_id": project.id,
        "name": project.name,
        "full_name": getattr(project, "name_with_namespace", None) or project.path_with_namespace,
        "description": getattr(project, "description", None) or "",
        "default_branch": getattr(project, "default_branch", None) or "main",
        "web_url": project.web_url,
        "ssh_url": project.ssh_url_to_repo,
        "http_url": project.http_url_to_repo,
        "is_archived": getattr(project, "archived", False),
        "is_private": getattr(project, "visibility", "private") == "private",
        "language": None,  # GitLab API has no dedicated language field at project level
    }


def _escape_html(text: str) -> str:
    """Minimal HTML-escaping for wrapping raw README content in <pre>."""
    return _html_module.escape(text)


# ---------------------------------------------------------------------------
# GitLabSourceProvider
# ---------------------------------------------------------------------------


class GitLabSourceProvider(BaseSourceProvider):
    """
    GitLab implementation of BaseSourceProvider.

    Uses python-gitlab to discover groups, projects, releases, READMEs, and
    commit metadata.  Supports both gitlab.com (cloud) and self-hosted
    GitLab instances.

    Args:
        provider: SourceProvider ORM model instance.
        credential_secret: Decrypted GitLab personal access token.
    """

    def __init__(self, provider, credential_secret: str) -> None:
        super().__init__(provider, credential_secret)
        # Determine the GitLab instance URL from the credential base_url
        # or fall back to gitlab.com for cloud.
        base_url = "https://gitlab.com"
        if self.provider.credential is not None and getattr(
            self.provider.credential, "base_url", None
        ):
            base_url = self.provider.credential.base_url.rstrip("/")

        self._base_url = base_url
        self._client = gitlab.Gitlab(url=base_url, private_token=self.credential_secret)

    def __repr__(self) -> str:
        return (
            f"<GitLabSourceProvider(provider_id={self.provider.id}, "
            f"base_url='{self._base_url}', "
            f"token='***')>"
        )

    # -- client factory -----------------------------------------------------

    def _get_client(self) -> gitlab.Gitlab:
        """Return the pre-initialized python-gitlab client."""
        return self._client

    # -- BaseSourceProvider interface ---------------------------------------

    async def check_access(self) -> bool:
        """
        Verify the credential by fetching the authenticated user.

        Returns:
            True on success.

        Raises:
            DomainException: If authentication or connectivity fails.
        """
        try:
            gl = self._get_client()

            def _check():
                gl.auth()
                return True

            return await asyncio.to_thread(_check)
        except GitlabError as exc:
            raise _map_gitlab_exception(exc, "check_access") from exc

    # -- groups -------------------------------------------------------------

    async def list_groups(self) -> list[dict]:
        """
        List all accessible GitLab groups and subgroups.

        Returns:
            List of group dicts with keys: external_id, name, full_name,
            full_path, description, web_url, avatar_url, parent_id.
        """
        gl = self._get_client()
        groups: list[dict] = []

        try:

            def _fetch():
                return gl.groups.list(all=True)

            raw_groups = await asyncio.to_thread(_fetch)
            for group in raw_groups:
                groups.append(_group_to_dict(group))

        except GitlabError as exc:
            raise _map_gitlab_exception(exc, "list_groups") from exc

        logger.info(
            "GitLab list_groups returned %d groups for provider %d",
            len(groups),
            self.provider.id,
        )
        return groups

    # -- repositories -------------------------------------------------------

    async def list_repositories(self, group_external_id: str) -> list[dict]:
        """
        List all projects within a given GitLab group.

        Args:
            group_external_id: The GitLab group ID (integer).

        Returns:
            List of repository dicts with keys: external_id, name,
            full_name, description, default_branch, web_url, ssh_url,
            http_url, is_archived, is_private, language.
        """
        gl = self._get_client()
        repositories: list[dict] = []

        try:

            def _fetch():
                gid = int(group_external_id)
                group = gl.groups.get(gid)
                return group.projects.list(all=True)

            raw_projects = await asyncio.to_thread(_fetch)
            for project in raw_projects:
                repositories.append(_project_to_dict(project))

        except (ValueError, TypeError) as exc:
            raise DomainException(
                f"Invalid group_external_id '{group_external_id}': must be an integer",
                status_code=400,
            ) from exc
        except GitlabError as exc:
            raise _map_gitlab_exception(exc, f"list_repositories/{group_external_id}") from exc

        logger.info(
            "GitLab list_repositories returned %d projects for group '%s'",
            len(repositories),
            group_external_id,
        )
        return repositories

    # -- single repository --------------------------------------------------

    async def get_repository(self, repo_external_id: str) -> dict:
        """
        Get detailed information for a single GitLab project, including
        license, README, and latest release.

        repo_external_id is the project path_with_namespace
        (equivalent to "owner/repo" on GitHub).

        Args:
            repo_external_id: Project path with namespace (e.g. "mygroup/myproject").

        Returns:
            Dict with repository metadata including license_spdx,
            license_name, readme_html, latest_release_tag,
            latest_release_name, latest_release_published_at,
            latest_release_author, latest_release_html_url.
        """
        gl = self._get_client()

        try:

            def _fetch_basic():
                return gl.projects.get(repo_external_id)

            project = await asyncio.to_thread(_fetch_basic)

            # License resolution
            license_spdx, license_name = _resolve_license_spdx(getattr(project, "license", None))

            # README -- fetch raw and wrap as HTML
            readme_html: str | None = None
            try:

                def _fetch_readme():
                    return project.repository_raw(file_path="README.md")

                readme_raw = await asyncio.to_thread(_fetch_readme)
                if readme_raw:
                    readme_html = (
                        '<div class="gitlab-readme">'
                        "<pre>" + _escape_html(readme_raw) + "</pre>"
                        "</div>"
                    )
            except GitlabError:
                logger.debug(
                    "No README.md found for project '%s'",
                    repo_external_id,
                )

            # Latest release
            latest_release_tag: str | None = None
            latest_release_name: str | None = None
            latest_release_published_at: str | None = None
            latest_release_author: str | None = None
            latest_release_html_url: str | None = None

            try:

                def _fetch_releases():
                    return project.releases.list(per_page=1, order_by="released_at", sort="desc")

                releases = await asyncio.to_thread(_fetch_releases)
                if releases:
                    release = releases[0]
                    latest_release_tag = getattr(release, "tag_name", None)
                    latest_release_name = getattr(release, "name", None)
                    latest_release_published_at = (
                        getattr(release, "released_at", None).isoformat()
                        if getattr(release, "released_at", None)
                        else None
                    )
                    latest_release_author = (
                        release.author.get("name") if getattr(release, "author", None) else None
                    )
                    latest_release_html_url = (
                        f"{project.web_url}/-/releases/{latest_release_tag}"
                        if latest_release_tag
                        else None
                    )
            except GitlabError:
                logger.debug(
                    "Failed to fetch releases for project '%s'",
                    repo_external_id,
                    exc_info=True,
                )

            result = {
                **_project_to_dict(project),
                "license_spdx": license_spdx,
                "license_name": license_name,
                "readme_html": readme_html,
                "latest_release_tag": latest_release_tag,
                "latest_release_name": latest_release_name,
                "latest_release_published_at": latest_release_published_at,
                "latest_release_author": latest_release_author,
                "latest_release_html_url": latest_release_html_url,
            }

        except GitlabError as exc:
            raise _map_gitlab_exception(exc, f"get_repository/{repo_external_id}") from exc

        logger.debug("GitLab get_repository OK for '%s'", repo_external_id)
        return result

    # -- commit info --------------------------------------------------------

    async def get_commit_info(self, repo_external_id: str, ref: str | None = None) -> dict:
        """
        Get metadata about the most recent commit on a GitLab project.

        Args:
            repo_external_id: Project path with namespace (e.g. "mygroup/myproject").
            ref: Optional branch name, tag name, or commit SHA. When
                 None, the project default branch is used.

        Returns:
            Dict with keys sha, date, author, message.
        """
        gl = self._get_client()

        try:

            def _fetch():
                project = gl.projects.get(repo_external_id)
                kwargs = {}
                if ref is not None:
                    kwargs["ref_name"] = ref
                commits = project.commits.list(per_page=1, **kwargs)
                if not commits:
                    raise DomainException(
                        f"No commits found for project '{repo_external_id}'"
                        + (f" (ref={ref})" if ref else ""),
                        status_code=404,
                    )
                commit = commits[0]
                return {
                    "sha": commit.id,
                    "date": getattr(commit, "created_at", None),
                    "author": getattr(commit, "author_name", None),
                    "message": getattr(commit, "message", None),
                }

            result = await asyncio.to_thread(_fetch)

        except DomainException:
            raise
        except GitlabError as exc:
            raise _map_gitlab_exception(exc, f"get_commit_info/{repo_external_id}") from exc

        logger.debug(
            "GitLab get_commit_info OK for '%s' (ref=%s)",
            repo_external_id,
            ref or "default",
        )
        return result

    # -- import single group ------------------------------------------------

    async def import_group(self, group_external_id: str | int) -> dict:
        """
        Get detailed information for a single GitLab group by ID.

        Args:
            group_external_id: The GitLab group ID.

        Returns:
            A group dict with the same format as list_groups.
        """
        gl = self._get_client()

        try:

            def _fetch():
                gid = int(group_external_id)
                return gl.groups.get(gid)

            group = await asyncio.to_thread(_fetch)
            result = _group_to_dict(group)

        except (ValueError, TypeError) as exc:
            raise DomainException(
                f"Invalid group_external_id '{group_external_id}': must be an integer",
                status_code=400,
            ) from exc
        except GitlabError as exc:
            raise _map_gitlab_exception(exc, f"import_group/{group_external_id}") from exc

        logger.info(
            "GitLab import_group OK for group '%s' (name='%s')",
            group_external_id,
            result.get("name", "?"),
        )
        return result
