"""
@file source_providers/github.py
@description GitHub concrete implementation of BaseSourceProvider.
             Discovers organizations, users, repositories, and commit
             metadata via the PyGithub library.
@dependencies PyGithub (github.Github, github.GithubException),
               app.core.exceptions.DomainException,
               app.services.source_provider.BaseSourceProvider
@relatedFiles ../source_provider.py, ../../models/source_provider.py,
               ../../models/source_group.py, ../../models/source_repository.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from github import Github, GithubException

from app.core.exceptions import DomainException
from app.services.source_provider import BaseSourceProvider

if TYPE_CHECKING:
    from app.models.source_provider import SourceProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _map_github_exception(exc: GithubException, operation: str) -> DomainException:
    """
    Map a :class:`github.GithubException` to a :class:`DomainException`
    with an appropriate HTTP status code and human-readable message.
    """
    status = exc.status if hasattr(exc, "status") else 0
    data = exc.data if hasattr(exc, "data") else {}
    message = data.get("message", str(exc))

    if status == 401:
        return DomainException(
            f"GitHub authentication failed during {operation}: {message}",
            status_code=401,
        )
    if status == 403 and ("rate limit" in message.lower() or "API rate limit" in message):
        return DomainException(
            f"GitHub rate limit exceeded during {operation}: {message}",
            status_code=429,
        )
    if status == 403:
        return DomainException(
            f"GitHub access forbidden during {operation}: {message}",
            status_code=403,
        )
    if status == 404:
        return DomainException(
            f"GitHub resource not found during {operation}: {message}",
            status_code=404,
        )
    if status == 422:
        return DomainException(
            f"GitHub validation failed during {operation}: {message}",
            status_code=422,
        )

    return DomainException(
        f"GitHub API error during {operation} (status={status}): {message}",
        status_code=502,
    )


def _repo_to_dict(repo, include_extra: bool = False) -> dict:
    """
    Convert a PyGithub ``Repository`` object to a flat dict.

    Args:
        repo: A :class:`github.Repository.Repository` instance.
        include_extra: When ``True``, include additional fields that are
                       only returned by :meth:`~GitHubSourceProvider.get_repository`
                       (``has_wiki``, ``topics``, ``size``, etc.).

    Returns:
        Dict with repository metadata.
    """
    result: dict = {
        "external_id": repo.id,
        "name": repo.name,
        "full_name": repo.full_name,
        "description": repo.description,
        "private": repo.private,
        "fork": repo.fork,
        "archived": repo.archived,
        "disabled": getattr(repo, "disabled", False),
        "language": repo.language,
        "default_branch": repo.default_branch,
        "html_url": repo.html_url,
        "clone_url": repo.clone_url,
        "ssh_url": repo.ssh_url,
        "stars": repo.stargazers_count,
        "forks": repo.forks_count,
        "open_issues": repo.open_issues_count,
        "created_at": repo.created_at,
        "updated_at": repo.updated_at,
        "pushed_at": repo.pushed_at,
        # Last commit — fetched lazily below
        "last_commit_sha": None,
        "last_commit_date": None,
        "last_commit_author": None,
        # License
        "license_spdx": repo.license.spdx_id if repo.license else None,
        "license_name": repo.license.name if repo.license else None,
        # Releases (use totalCount to avoid loading all releases)
        "releases_count": (
            repo.get_releases().totalCount
            if hasattr(repo, "get_releases")
            else 0
        ),
    }

    if include_extra:
        result.update(
            {
                "has_wiki": repo.has_wiki,
                "has_pages": repo.has_pages,
                "has_issues": repo.has_issues,
                "has_projects": repo.has_projects,
                "topics": getattr(repo, "topics", []),
                "size": repo.size,
                "subscribers_count": repo.subscribers_count,
                "network_count": repo.network_count,
                "allow_forking": getattr(repo, "allow_forking", False),
                "web_commit_signoff_required": getattr(
                    repo, "web_commit_signoff_required", False
                ),
            }
        )

    # Try to fetch the last commit on the default branch
    try:
        if repo.default_branch:
            branch = repo.get_branch(repo.default_branch)
            commit = branch.commit
            result["last_commit_sha"] = commit.sha
            result["last_commit_date"] = commit.commit.author.date
            result["last_commit_author"] = commit.commit.author.name
    except GithubException:
        logger.debug(
            "Failed to fetch last commit for repo %s", repo.full_name, exc_info=True
        )

    return result


# ---------------------------------------------------------------------------
# GitHubSourceProvider
# ---------------------------------------------------------------------------


class GitHubSourceProvider(BaseSourceProvider):
    """
    GitHub implementation of :class:`BaseSourceProvider`.

    Uses PyGithub to discover organizations, users, repositories, and commit
    metadata.  Supports both ``organization`` and ``user`` provider types,
    automatically treating the authenticated user's account as a group.

    Args:
        provider: :class:`SourceProvider` ORM model.
        credential_secret: Decrypted GitHub personal access token.
    """

    # -- client factory -----------------------------------------------------

    def _get_client(self) -> Github:
        """Build a PyGithub client using the decrypted credential secret."""
        return Github(self.credential_secret)

    # -- BaseSourceProvider interface ---------------------------------------

    async def check_access(self) -> bool:
        """
        Verify the credential by fetching the authenticated user's login.

        Returns:
            ``True`` on success.
        """
        try:
            gh = self._get_client()
            user = gh.get_user()
            login = user.login
            logger.info("GitHub check_access OK for user '%s'", login)
            return True
        except GithubException as exc:
            raise _map_github_exception(exc, "check_access") from exc

    # -- groups -------------------------------------------------------------

    async def list_groups(self) -> list[dict]:
        """
        List all accessible groups: organizations + the authenticated user.

        The authenticated user is always returned as the first element
        (treated as a "user" organization), followed by all organizations
        the token can see.

        Returns:
            List of group dicts.
        """
        gh = self._get_client()
        groups: list[dict] = []

        try:
            user = gh.get_user()

            # 1. Authenticated user as a pseudo-organization
            groups.append(
                {
                    "external_id": user.login,
                    "name": user.name or user.login,
                    "full_name": user.login,
                    "description": getattr(user, "bio", None),
                    "avatar_url": user.avatar_url,
                    "public_repos": user.public_repos,
                    "total_private_repos": user.total_private_repos,
                    "html_url": user.html_url,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                }
            )

            # 2. Organizations the user belongs to
            try:
                orgs = list(user.get_orgs())
                for org in orgs:
                    groups.append(
                        {
                            "external_id": org.login,
                            "name": org.name or org.login,
                            "full_name": org.login,
                            "description": org.description,
                            "avatar_url": org.avatar_url,
                            "public_repos": org.public_repos,
                            "total_private_repos": getattr(
                                org, "total_private_repos", 0
                            ),
                            "html_url": org.html_url,
                            "created_at": org.created_at,
                            "updated_at": org.updated_at,
                        }
                    )
            except GithubException:
                logger.warning(
                    "Failed to list organizations for user '%s'",
                    user.login,
                    exc_info=True,
                )

        except GithubException as exc:
            raise _map_github_exception(exc, "list_groups") from exc

        logger.info(
            "GitHub list_groups returned %d groups for provider %d",
            len(groups),
            self.provider.id,
        )
        return groups

    # -- repositories -------------------------------------------------------

    async def list_repositories(self, group_external_id: str) -> list[dict]:
        """
        List all repositories for a group (organization or user).

        Yields across all pages — the underlying GitHub API returns up
        to 100 items per page.

        Args:
            group_external_id: GitHub login of the organization or user.

        Returns:
            List of repository dicts.
        """
        gh = self._get_client()
        repositories: list[dict] = []

        try:
            owner = gh.get_user(group_external_id)
            repos = list(owner.get_repos())
            for repo in repos:
                repositories.append(_repo_to_dict(repo))
        except GithubException as exc:
            raise _map_github_exception(exc, f"list_repositories/{group_external_id}") from exc

        logger.info(
            "GitHub list_repositories returned %d repos for '%s'",
            len(repositories),
            group_external_id,
        )
        return repositories

    # -- single repository --------------------------------------------------

    async def get_repository(self, repo_external_id: str) -> dict:
        """
        Get detailed information for a single repository.

        Args:
            repo_external_id: Full repository name (``"owner/repo"``).

        Returns:
            Dict with all standard repository fields plus extended metadata
            (wiki, pages, issues, projects, topics, size, subscribers, etc.).
        """
        gh = self._get_client()

        try:
            repo = gh.get_repo(repo_external_id)
            result = _repo_to_dict(repo, include_extra=True)
        except GithubException as exc:
            raise _map_github_exception(exc, f"get_repository/{repo_external_id}") from exc

        logger.debug("GitHub get_repository OK for '%s'", repo_external_id)
        return result

    # -- commit info --------------------------------------------------------

    async def get_commit_info(
        self, repo_external_id: str, ref: str | None = None
    ) -> dict:
        """
        Get metadata about the most recent commit on a repository.

        Args:
            repo_external_id: Full repository name (``"owner/repo"``).
            ref: Optional branch name, tag name, or commit SHA.  When
                 ``None``, the repository's default branch is used.

        Returns:
            Dict with keys ``sha``, ``date``, ``author``, ``message``.
        """
        gh = self._get_client()

        try:
            repo = gh.get_repo(repo_external_id)

            # Resolve the target ref
            if ref is not None:
                try:
                    commit = repo.get_commit(ref)
                except GithubException:
                    # ref might be a branch name — try via get_branch
                    try:
                        branch = repo.get_branch(ref)
                        commit = branch.commit
                    except GithubException:
                        raise DomainException(
                            f"Ref '{ref}' not found in repository '{repo_external_id}'",
                            status_code=404,
                        )
            else:
                branch = repo.get_branch(repo.default_branch)
                commit = branch.commit

            result = {
                "sha": commit.sha,
                "date": commit.commit.author.date,
                "author": commit.commit.author.name,
                "message": commit.commit.message,
            }
        except GithubException as exc:
            raise _map_github_exception(exc, f"get_commit_info/{repo_external_id}") from exc

        logger.debug(
            "GitHub get_commit_info OK for '%s' (ref=%s)",
            repo_external_id,
            ref or repo.default_branch,
        )
        return result
