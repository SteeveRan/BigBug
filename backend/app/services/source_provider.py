"""
@file source_provider.py
@description Abstract base class for source providers (GitHub, GitLab, BitBucket, etc.).
             Defines the interface that all source provider implementations must satisfy.
@dependencies abc, app.models.source_provider.SourceProvider
@relatedFiles ./source_providers/github.py, ../models/source_provider.py
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.source_provider import SourceProvider


class BaseSourceProvider(ABC):
    """
    Abstract base class for source providers.

    Each concrete implementation (GitHub, GitLab, BitBucket, etc.) provides
    discovery and metadata retrieval for groups (organizations/users) and
    repositories within those groups.

    Args:
        provider: The :class:`SourceProvider` ORM model instance with provider
                  configuration (type, credential reference, etc.).
        credential_secret: The *decrypted* secret string (e.g. a GitHub
                           personal access token). The caller is responsible
                           for decrypting the value read from the database
                           before passing it here.
    """

    def __init__(self, provider: SourceProvider, credential_secret: str) -> None:
        self.provider = provider
        self.credential_secret = credential_secret

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def list_groups(self) -> list[dict]:
        """
        List all groups (organizations + user account) accessible with the
        current credential.

        Returns:
            List of dicts, each representing a group with at least:
            ``external_id``, ``name``, ``full_name``, ``description``,
            ``avatar_url``, ``public_repos``, ``total_private_repos``,
            ``html_url``, ``created_at``, ``updated_at``.
        """
        ...

    @abstractmethod
    async def list_repositories(self, group_external_id: str) -> list[dict]:
        """
        List all repositories within a given group.

        Args:
            group_external_id: The external identifier of the group
                               (e.g. GitHub organization login or username).

        Returns:
            List of dicts, each representing a repository with at least:
            ``external_id``, ``name``, ``full_name``, ``description``,
            ``private``, ``fork``, ``archived``, ``disabled``,
            ``language``, ``default_branch``, ``html_url``, ``clone_url``,
            ``ssh_url``, ``stars``, ``forks``, ``open_issues``,
            ``created_at``, ``updated_at``, ``pushed_at``,
            ``last_commit_sha``, ``last_commit_date``,
            ``last_commit_author``, ``license_spdx``, ``license_name``,
            ``releases_count``.
        """
        ...

    @abstractmethod
    async def get_repository(self, repo_external_id: str) -> dict:
        """
        Get detailed information about a single repository.

        Args:
            repo_external_id: The external identifier of the repository
                              (e.g. ``"owner/repo"`` on GitHub).

        Returns:
            Dict with all fields from :meth:`list_repositories` plus:
            ``has_wiki``, ``has_pages``, ``has_issues``, ``has_projects``,
            ``topics``, ``size``, ``subscribers_count``, ``network_count``,
            ``allow_forking``, ``web_commit_signoff_required``.
        """
        ...

    @abstractmethod
    async def get_commit_info(self, repo_external_id: str, ref: str | None = None) -> dict:
        """
        Get information about the most recent commit on a repository.

        Args:
            repo_external_id: The external identifier of the repository
                              (e.g. ``"owner/repo"`` on GitHub).
            ref: Optional branch name, tag name, or commit SHA. When
                 ``None``, the default branch is used.

        Returns:
            Dict with: ``sha``, ``date``, ``author``, ``message``.
        """
        ...

    @abstractmethod
    async def check_access(self) -> bool:
        """
        Verify that the configured credential can access the source provider.

        Returns:
            ``True`` if the credential is valid, otherwise an exception
            should be raised.
        """
        ...
