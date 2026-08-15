"""
@file gitlab.py
@description GitLab service — provider resolution and client factory.
             Resolves the default platform GitLab from ``resource_providers``
             (subtype=gitlab, category=system, direction=internal); falls back
             to settings.GITLAB_URL / settings.GITLAB_TOKEN for backward
             compatibility when no provider is configured.
@dependencies python-gitlab, app.config.settings, app.core.secrets
@relatedFiles ../models/resource_provider.py, ../core/secrets.py
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import gitlab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.config import settings
from app.core.exceptions import BadRequestError
from app.core.secrets import decrypt_secret

if TYPE_CHECKING:
    from app.models.resource_provider import ResourceProvider


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


async def get_default_gitlab_provider(db: AsyncSession) -> ResourceProvider | None:
    """Return the default platform GitLab from ``resource_providers``.

    Providers V3 rule (plans/features/providers-unified.md 11.3.4): the
    platform GitLab is a ``resource_providers`` row with subtype=gitlab,
    category=system and direction=internal. Prefer ``is_default``, then the
    first active row by id ASC. The credential is eager-loaded so callers can
    decrypt the token without an async lazy load.
    """
    from app.models.resource_provider import (
        ProviderCategory,
        ProviderDirection,
        ProviderSubtype,
        ResourceProvider,
    )

    stmt = (
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
    # Prefer the default, then the earliest created.
    default = await db.execute(stmt.where(ResourceProvider.is_default.is_(True)).limit(1))
    provider = default.unique().scalar_one_or_none()
    if provider is not None:
        return provider
    result = await db.execute(stmt.order_by(ResourceProvider.id.asc()).limit(1))
    return result.unique().scalar_one_or_none()


class GitLabService:
    """Service for interacting with the platform GitLab provider."""

    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    @staticmethod
    async def get_default_instance(db: AsyncSession) -> ResourceProvider | None:
        """Return the default platform GitLab provider from resource_providers."""
        return await get_default_gitlab_provider(db)

    # ------------------------------------------------------------------
    # Client factory
    # ------------------------------------------------------------------

    def _get_client(self, provider: ResourceProvider | None = None) -> gitlab.Gitlab:
        """
        Build a python-gitlab client.

        Priority:
        1. ``provider`` — use its base_url and *decrypted* credential secret.
        2. ``settings.gitlab_url`` and ``settings.gitlab_token`` (fallback).
        3. ``settings.gitlab_url`` without auth.
        """
        if provider is not None:
            token: str | None = None
            if provider.credential is not None and provider.credential.encrypted_secret:
                token = decrypt_secret(provider.credential.encrypted_secret)
            return gitlab.Gitlab(
                provider.base_url,
                private_token=token or None,
                ssl_verify=provider.verify_ssl,
            )

        # Backward-compatible fallback
        if settings.gitlab_url:
            return gitlab.Gitlab(
                settings.gitlab_url,
                private_token=settings.gitlab_token or None,
            )
        return gitlab.Gitlab()


# Module-level singleton (backward-compatible)
gitlab_service = GitLabService()
