"""GitLab client factories for pipeline runs.

Providers V3 (phase 7A): the platform GitLab is a system/internal
``ResourceProvider``; the legacy ``GitlabInstance`` path is gone.
"""

from __future__ import annotations

import gitlab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.secrets import decrypt_secret
from app.models.pipeline_run import PipelineRun
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderSubtype,
    ResourceProvider,
)


def _get_provider_gitlab_client(provider: ResourceProvider) -> gitlab.Gitlab:
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


async def _get_pipeline_provider_or_404(db: AsyncSession, provider_id: int) -> ResourceProvider:
    """Fetch and validate a resource provider for pipeline usage.

    Providers V3 rule (plans/features/providers-unified.md 11.3.4):
    ``pipelines.provider_id`` must reference a gitlab provider with
    category=system and direction=internal — the platform's own GitLab is
    the only provider allowed to trigger pipelines.
    """
    result = await db.execute(
        select(ResourceProvider)
        .options(joinedload(ResourceProvider.credential))
        .where(
            ResourceProvider.id == provider_id,
            ~ResourceProvider.is_deleted,
        )
    )
    provider = result.unique().scalar_one_or_none()
    if provider is None:
        raise NotFoundError(f"Provider with id={provider_id} not found")
    if (
        provider.subtype != ProviderSubtype.gitlab
        or provider.category != ProviderCategory.system
        or provider.direction != ProviderDirection.internal
    ):
        raise BadRequestError(
            f"Provider {provider_id} ({provider.subtype}/{provider.category}/"
            f"{provider.direction}) cannot run pipelines: pipelines require a "
            "gitlab provider with category=system and direction=internal"
        )
    return provider


async def _get_client_for_run(db: AsyncSession, run: PipelineRun) -> gitlab.Gitlab:
    """Build a python-gitlab client for a run's system/internal GitLab provider."""
    if run.provider_id is None:
        raise NotFoundError(
            f"PipelineRun {run.id} has no provider_id — cannot build a GitLab client"
        )
    result = await db.execute(
        select(ResourceProvider)
        .options(joinedload(ResourceProvider.credential))
        .where(ResourceProvider.id == run.provider_id)
    )
    provider = result.unique().scalar_one_or_none()
    if provider is None:
        raise NotFoundError(f"Provider with id={run.provider_id} not found for run {run.id}")
    return _get_provider_gitlab_client(provider)
