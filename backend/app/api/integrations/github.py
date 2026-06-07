"""
@file integrations/github.py
@description REST API for GitHub instance management.
@dependencies app.services.integrations (GithubInstanceService), app.core.rbac
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
    GithubInstanceCreate,
    GithubInstanceOut,
    GithubInstanceUpdate,
)
from app.services.audit import AuditService
from app.services.integrations import GithubInstanceService

router = APIRouter()
_manage = Depends(require_permission("integrations:manage"))


@router.get("/github", response_model=list[GithubInstanceOut])
async def list_github_instances(
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """List all configured GitHub instances."""
    service = GithubInstanceService(db)
    return await service.list_instances()


@router.post("/github", response_model=GithubInstanceOut, status_code=status.HTTP_201_CREATED)
async def create_github_instance(
    data: GithubInstanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _manage,
):
    """Register a new GitHub instance (token)."""
    service = GithubInstanceService(db)
    try:
        result = await service.create_instance(
            name=data.name,
            token=data.token,
            is_active=data.is_active,
            is_default=data.is_default,
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


@router.get("/github/{instance_id}", response_model=GithubInstanceOut)
async def get_github_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Get a single GitHub instance by ID."""
    service = GithubInstanceService(db)
    try:
        return await service.get_instance(instance_id)
    except NotFoundError as e:
        raise e


@router.patch("/github/{instance_id}", response_model=GithubInstanceOut)
async def update_github_instance(
    instance_id: int,
    data: GithubInstanceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _manage,
):
    """Update an existing GitHub instance (partial)."""
    service = GithubInstanceService(db)
    try:
        result = await service.update_instance(
            instance_id=instance_id,
            name=data.name,
            token=data.token,
            is_active=data.is_active,
            is_default=data.is_default,
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


@router.delete("/github/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_github_instance(
    instance_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _manage,
):
    """Delete a GitHub instance."""
    service = GithubInstanceService(db)
    try:
        instance = await service.get_instance(instance_id)
        instance_name = instance.name
    except NotFoundError:
        instance_name = f"github_{instance_id}"

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


@router.post("/github/{instance_id}/test", response_model=ConnectionTestResult)
async def test_github_connection(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Test connectivity to the GitHub API and update the instance status."""
    service = GithubInstanceService(db)
    try:
        return await service.test_connection(instance_id)
    except NotFoundError as e:
        raise e
