"""GitLab client factories for pipeline runs.

Providers V3 (phase 7A): the platform GitLab is a system/internal
``ResourceProvider``; the legacy ``GitlabInstance`` path is gone.

The provider client factory has moved to ``app.services.gitlab_projects._clients``
and is re-exported here for backward compatibility. The former system-only
trigger restriction is lifted: any live gitlab provider may now run pipelines,
and the run's provider is derived from its gitlab project when available.
"""

from __future__ import annotations

import gitlab
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.pipeline_run import PipelineRun
from app.models.resource_provider import ResourceProvider
from app.services.gitlab_projects._clients import (
    _get_gitlab_provider_or_404,
    get_provider_gitlab_client,
)

# Backward-compatible aliases (the historical private names).
_get_provider_gitlab_client = get_provider_gitlab_client


async def _get_pipeline_provider_or_404(db: AsyncSession, provider_id: int) -> ResourceProvider:
    """Fetch and validate a resource provider for pipeline usage.

    Providers V3 (gitlab-project-management): any live ``gitlab`` provider is
    allowed. The caller's ownership/type access matrix is enforced upstream in
    the service layer; this helper only guarantees subtype=gitlab + not deleted.
    """
    return await _get_gitlab_provider_or_404(db, provider_id)


async def _get_client_for_run(db: AsyncSession, run: PipelineRun) -> gitlab.Gitlab:
    """Build a python-gitlab client for a run's gitlab provider."""
    if run.provider_id is None:
        raise NotFoundError(
            f"PipelineRun {run.id} has no provider_id — cannot build a GitLab client"
        )
    provider = await _get_gitlab_provider_or_404(db, run.provider_id)
    return _get_provider_gitlab_client(provider)
