"""
@file gitlab.py
@description GitLab service — instance resolution and client factory.
             Supports multi-instance: accepts an optional ``instance`` parameter;
             falls back to the first active DB instance, then to settings.GITLAB_URL
             / settings.GITLAB_TOKEN for backward compatibility.
@dependencies python-gitlab, app.config.settings, app.core.secrets,
               app.services.integrations.get_default_gitlab_instance
@relatedFiles ../models/gitlab_instance.py, ../core/secrets.py, ./integrations.py
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import gitlab
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError
from app.core.secrets import decrypt_secret

if TYPE_CHECKING:
    from app.models.gitlab_instance import GitlabInstance


def _parse_gitlab_url(url: str) -> tuple[str, str]:
    """Parse a GitLab URL and return (namespace, project_name)."""
    patterns = [
        r"gitlab[^/]*/([^/]+/[^/\.]+?)(?:\.git)?$",
        r"([^/]+/[^/\.]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            parts = match.group(1).split("/")
            if len(parts) >= 2:
                return "/".join(parts[:-1]), parts[-1]
    raise BadRequestError(f"Cannot parse GitLab URL: {url}")


class GitLabService:
    """Service for interacting with GitLab instances."""

    # ------------------------------------------------------------------
    # Instance resolution
    # ------------------------------------------------------------------

    @staticmethod
    async def get_default_instance(db: AsyncSession) -> GitlabInstance | None:
        """Return the first active GitLab instance from the database."""
        from app.services.integrations import get_default_gitlab_instance

        return await get_default_gitlab_instance(db)

    # ------------------------------------------------------------------
    # Client factory
    # ------------------------------------------------------------------

    def _get_client(self, instance: GitlabInstance | None = None) -> gitlab.Gitlab:
        """
        Build a python-gitlab client.

        Priority:
        1. ``instance`` — use its URL and *decrypted* token.
        2. ``settings.gitlab_url`` and ``settings.gitlab_token`` (fallback).
        3. ``settings.gitlab_url`` without auth.
        """
        if instance is not None:
            token = decrypt_secret(instance.token) if instance.token else None
            return gitlab.Gitlab(instance.url, private_token=token or None)

        # Backward-compatible fallback
        if settings.gitlab_url:
            return gitlab.Gitlab(
                settings.gitlab_url,
                private_token=settings.gitlab_token or None,
            )
        return gitlab.Gitlab()


# Module-level singleton (backward-compatible)
gitlab_service = GitLabService()
