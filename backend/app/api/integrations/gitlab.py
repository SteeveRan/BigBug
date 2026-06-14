"""
@file integrations/gitlab.py
@description REST API for GitLab instance management.
@dependencies app.services.integrations (GitlabInstanceService), app.core.rbac
@relatedFiles __init__.py
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.rbac import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.integrations import (
    ConnectionTestResult,
    GitlabInstanceCreate,
    GitlabInstanceOut,
    GitlabInstanceUpdate,
)
from app.services.audit import AuditService
from app.services.integrations import GitlabInstanceService

router = APIRouter()
_read = Depends(require_permission("integrations:read"))
_write = Depends(require_permission("integrations:write"))


@router.get("/gitlab", response_model=list[GitlabInstanceOut])
async def list_gitlab_instances(
    db: AsyncSession = Depends(get_db),
    _: User = _read,
):
    """List all configured GitLab instances."""
    service = GitlabInstanceService(db)
    return await service.list_instances()


@router.post("/gitlab", response_model=GitlabInstanceOut, status_code=status.HTTP_201_CREATED)
async def create_gitlab_instance(
    data: GitlabInstanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _write,
):
    """Register a new GitLab instance."""
    service = GitlabInstanceService(db)
    try:
        result = await service.create_instance(
            name=data.name,
            url=data.url,
            token=data.token,
            is_active=data.is_active,
            verify_ssl=data.verify_ssl,
            is_default=data.is_default,
            default_group_id=data.default_group_id,
        )
    except ConflictError as e:
        raise e

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="create",
        resource_type="integration",
        resource_id=result.id,
        resource_name=result.name,
        ip_address=request.client.host if request.client else None,
    )

    return result


@router.get("/gitlab/{instance_id}", response_model=GitlabInstanceOut)
async def get_gitlab_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _read,
):
    """Get a single GitLab instance by ID."""
    service = GitlabInstanceService(db)
    try:
        return await service.get_instance(instance_id)
    except NotFoundError as e:
        raise e


@router.patch("/gitlab/{instance_id}", response_model=GitlabInstanceOut)
async def update_gitlab_instance(
    instance_id: int,
    data: GitlabInstanceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _write,
):
    """Update an existing GitLab instance (partial)."""
    service = GitlabInstanceService(db)
    try:
        result = await service.update_instance(
            instance_id=instance_id,
            name=data.name,
            url=data.url,
            token=data.token,
            is_active=data.is_active,
            verify_ssl=data.verify_ssl,
            is_default=data.is_default,
            default_group_id=data.default_group_id,
        )
    except (NotFoundError, ConflictError) as e:
        raise e

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="update",
        resource_type="integration",
        resource_id=result.id,
        resource_name=result.name,
        ip_address=request.client.host if request.client else None,
    )

    return result


@router.delete("/gitlab/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gitlab_instance(
    instance_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _write,
):
    """Delete a GitLab instance."""
    service = GitlabInstanceService(db)
    try:
        instance = await service.get_instance(instance_id)
        instance_name = instance.name
    except NotFoundError:
        instance_name = f"gitlab_{instance_id}"

    try:
        await service.delete_instance(instance_id)
    except NotFoundError as e:
        raise e

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="delete",
        resource_type="integration",
        resource_id=instance_id,
        resource_name=instance_name,
        ip_address=request.client.host if request.client else None,
    )


@router.post("/gitlab/{instance_id}/test", response_model=ConnectionTestResult)
async def test_gitlab_connection(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _write,
):
    """Test connectivity to a GitLab instance and update its status."""
    service = GitlabInstanceService(db)
    try:
        return await service.test_connection(instance_id)
    except NotFoundError as e:
        raise e
