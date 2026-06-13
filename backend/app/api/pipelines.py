"""
@file pipelines.py
@description REST API for managing GitLab pipeline runs — triggering,
             cancelling, retrying, listing pipelines, and Pipeline Config CRUD
             (git-mirroring v2).
@dependencies app.services.pipeline, app.core.rbac (require_permission),
              app.schemas.pipeline
@relatedFiles ../services/pipeline.py, ../schemas/pipeline.py
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainException
from app.core.rbac import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineDuplicateRequest,
    PipelineOut,
    PipelineRunCreate,
    PipelineRunList,
    PipelineRunOut,
    PipelineUpdate,
)
from app.services import pipeline as pipeline_service

router = APIRouter()


# ─────────────────────────────────────────────────────────────────
# Pipeline Runs (existing)
# ─────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────
# Pipeline Config CRUD (git-mirroring v2)
# ─────────────────────────────────────────────────────────────────


@router.get("/configs", response_model=list[PipelineOut])
async def list_pipeline_configs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_enabled: bool | None = Query(None),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:read")),
):
    """List all Pipeline configurations with optional filtering and pagination."""
    configs = await pipeline_service.get_pipeline_configs(
        db, skip=skip, limit=limit, is_enabled=is_enabled, search=search
    )
    return [PipelineOut.model_validate(c) for c in configs]


@router.post("/configs", response_model=PipelineOut, status_code=201)
async def create_pipeline_config(
    data: PipelineCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:write")),
):
    """Create a new Pipeline configuration."""
    try:
        pipeline = await pipeline_service.create_pipeline(db, data)
    except DomainException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return PipelineOut.model_validate(pipeline)


@router.get("/configs/{pipeline_id}", response_model=PipelineOut)
async def get_pipeline_config_endpoint(
    pipeline_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:read")),
):
    """Get a single Pipeline configuration by ID."""
    pipeline = await pipeline_service.get_pipeline_config(db, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return PipelineOut.model_validate(pipeline)


@router.patch("/configs/{pipeline_id}", response_model=PipelineOut)
async def update_pipeline_config(
    pipeline_id: int,
    data: PipelineUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:write")),
):
    """Partially update a Pipeline configuration."""
    try:
        pipeline = await pipeline_service.update_pipeline(db, pipeline_id, data)
    except DomainException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return PipelineOut.model_validate(pipeline)


@router.delete("/configs/{pipeline_id}", status_code=204)
async def delete_pipeline_config(
    pipeline_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:delete")),
):
    """Delete a Pipeline configuration."""
    try:
        await pipeline_service.delete_pipeline(db, pipeline_id)
    except DomainException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/configs/{pipeline_id}/duplicate", response_model=PipelineOut)
async def duplicate_pipeline_config(
    pipeline_id: int,
    data: PipelineDuplicateRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:write")),
):
    """Duplicate a Pipeline under a new name."""
    try:
        pipeline = await pipeline_service.duplicate_pipeline(db, pipeline_id, data.name)
    except DomainException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return PipelineOut.model_validate(pipeline)


# ─────────────────────────────────────────────────────────────────
# Pipeline Runs (existing — individual run operations)
# ─────────────────────────────────────────────────────────────────


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
