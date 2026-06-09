"""
@file pipelines.py
@description REST API for managing GitLab pipeline runs — triggering,
             cancelling, retrying, and listing pipelines via the GitLab API.
@dependencies app.services.pipeline, app.core.rbac (require_permission),
              app.schemas.pipeline
@relatedFiles ../services/pipeline.py, ../schemas/pipeline.py
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.pipeline import PipelineRunCreate, PipelineRunList, PipelineRunOut
from app.services import pipeline as pipeline_service

router = APIRouter()


@router.get("", response_model=PipelineRunList)
async def list_pipeline_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: int | None = Query(None, ge=0, le=4),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:read")),
):
    """List pipeline runs with pagination and optional status filter."""
    items, total = await pipeline_service.get_pipeline_runs(
        db, page=page, page_size=page_size, status_filter=status
    )
    return PipelineRunList(
        items=[PipelineRunOut.model_validate(r) for r in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=PipelineRunOut, status_code=201)
async def trigger_pipeline(
    data: PipelineRunCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("pipelines:write")),
):
    """Trigger a new pipeline run in GitLab."""
    run = await pipeline_service.trigger_pipeline(
        db,
        gitlab_instance_id=data.gitlab_instance_id,
        gitlab_project_id=data.gitlab_project_id,
        ref=data.ref,
        variables=data.variables,
        user_id=current_user.id,
    )
    return PipelineRunOut.model_validate(run)


@router.get("/{run_id}", response_model=PipelineRunOut)
async def get_pipeline_run(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:read")),
):
    """Get details of a specific pipeline run."""
    run = await pipeline_service.get_pipeline_run(db, run_id)
    return PipelineRunOut.model_validate(run)


@router.post("/{run_id}/cancel", response_model=PipelineRunOut)
async def cancel_pipeline(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:delete")),
):
    """Cancel a running pipeline."""
    run = await pipeline_service.cancel_pipeline(db, run_id)
    return PipelineRunOut.model_validate(run)


@router.post("/{run_id}/retry", response_model=PipelineRunOut)
async def retry_pipeline(
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:write")),
):
    """Retry a failed pipeline."""
    run = await pipeline_service.retry_pipeline(db, run_id)
    return PipelineRunOut.model_validate(run)
