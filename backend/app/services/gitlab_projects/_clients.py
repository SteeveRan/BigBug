"""Shared python-gitlab client factory for gitlab-project management.

This module is the single source of truth for building a ``gitlab.Gitlab``
client out of a ``ResourceProvider``. ``pipeline/_clients.py`` re-exports the
helpers so the existing pipeline code keeps working while the provider
validation rules become more permissive (see ``_get_gitlab_provider_or_404``).
"""

from __future__ import annotations

import gitlab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import DomainError, NotFoundError
from app.core.secrets import decrypt_secret
from app.models.resource_provider import ProviderSubtype, ResourceProvider


def get_provider_gitlab_client(provider: ResourceProvider) -> gitlab.Gitlab:
    """Create a python-gitlab client for a ResourceProvider (git/gitlab).

    The provider's secret lives in its linked credential (Providers V3:
    secrets are stored only in ``credentials``). Public providers without a
    credential get an anonymous client.
    """
    token: str | None = None
    if provider.credential is not None and provider.credential.encrypted_secret:
        token = decrypt_secret(provider.credential.encrypted_secret)
    return gitlab.Gitlab(
        url=provider.base_url,
        private_token=token,
        ssl_verify=provider.verify_ssl,
        user_agent="BigBug/1.0",
    )


async def _get_gitlab_provider_or_404(
    db: AsyncSession, provider_id: int, *, load_credential: bool = True
) -> ResourceProvider:
    """Fetch a live gitlab ``ResourceProvider`` (subtype=gitlab, not deleted).

    Providers V3: gitlab projects/components/pipelines may live on any gitlab
    provider owned by the caller or the platform — ``category`` and
    ``direction`` are intentionally NOT restricted here. The owner/type access
    matrix is enforced by the service layer, not the client factory.
    """
    stmt = select(ResourceProvider).where(
        ResourceProvider.id == provider_id,
        ~ResourceProvider.is_deleted,
    )
    if load_credential:
        stmt = stmt.options(joinedload(ResourceProvider.credential))
    result = await db.execute(stmt)
    provider = result.unique().scalar_one_or_none()
    if provider is None:
        raise NotFoundError(f"Provider with id={provider_id} not found")
    if provider.subtype != ProviderSubtype.gitlab:
        raise DomainError(
            f"Provider {provider_id} is not a gitlab provider (subtype={provider.subtype.value})",
            422,
        )
    return provider
