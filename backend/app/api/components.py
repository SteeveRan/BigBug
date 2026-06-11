"""
@file components.py
@description REST API for managing GitLab CI/CD component registrations.
             Components represent reusable GitLab CI/CD templates.
@dependencies app.services.pipeline, app.core.rbac (require_permission),
              app.schemas.pipeline
@relatedFiles ../services/pipeline.py, ../schemas/pipeline.py
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.pipeline import (
    ComponentRunRequest,
    GitLabComponentCreate,
    GitLabComponentOut,
    GitLabComponentUpdate,
    PipelineRunOut,
)
from app.services import pipeline as pipeline_service

router = APIRouter()


@router.get("", response_model=list[GitLabComponentOut])
async def list_components(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:read")),
):
    """List all registered GitLab CI/CD components."""
    components = await pipeline_service.list_components(db)
    return [GitLabComponentOut.model_validate(c) for c in components]


@router.post("", response_model=GitLabComponentOut, status_code=201)
async def create_component(
    data: GitLabComponentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:write")),
):
    """Register a new GitLab CI/CD component."""
    component = await pipeline_service.create_component(
        db,
        name=data.name,
        description=data.description,
        gitlab_instance_id=data.gitlab_instance_id,
        project_path=data.project_path,
        component_path=data.component_path,
        version=data.version,
        inputs_schema=data.inputs_schema,
    )
    return GitLabComponentOut.model_validate(component)


@router.get("/{component_id}", response_model=GitLabComponentOut)
async def get_component(
    component_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:read")),
):
    """Get details of a specific GitLab component."""
    component = await pipeline_service.get_component(db, component_id)
    return GitLabComponentOut.model_validate(component)


@router.patch("/{component_id}", response_model=GitLabComponentOut)
async def update_component(
    component_id: int,
    data: GitLabComponentUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:write")),
):
    """Update an existing GitLab component."""
    component = await pipeline_service.update_component(
        db,
        component_id=component_id,
        name=data.name,
        description=data.description,
        gitlab_instance_id=data.gitlab_instance_id,
        project_path=data.project_path,
        component_path=data.component_path,
        version=data.version,
        inputs_schema=data.inputs_schema,
        is_enabled=data.is_enabled,
    )
    return GitLabComponentOut.model_validate(component)


@router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_component(
    component_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("pipelines:delete")),
):
    """Delete a GitLab component."""
    await pipeline_service.delete_component(db, component_id)


@router.post("/{component_id}/run", response_model=PipelineRunOut, status_code=201)
async def run_component(
    component_id: int,
    data: ComponentRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("pipelines:write")),
):
    """Trigger a pipeline run using a registered GitLab CI/CD component."""
    run = await pipeline_service.trigger_component(
        db,
        component_id=component_id,
        inputs=data.inputs,
        ref=data.ref,
        user_id=current_user.id,
    )
    return PipelineRunOut.model_validate(run)
