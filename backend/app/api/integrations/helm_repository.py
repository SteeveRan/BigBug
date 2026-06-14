"""
@file integrations/helm_repository.py
@description REST API for Helm Repository instance management.
@dependencies app.services.integrations (HelmRepositoryInstanceService), app.core.rbac
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
    HelmRepositoryInstanceCreate,
    HelmRepositoryInstanceOut,
    HelmRepositoryInstanceUpdate,
)
from app.services.audit import AuditService
from app.services.integrations import HelmRepositoryInstanceService

router = APIRouter()
_read = Depends(require_permission("integrations:read"))
_write = Depends(require_permission("integrations:write"))


@router.get("/helm-repository", response_model=list[HelmRepositoryInstanceOut])
async def list_helm_repository_instances(
    db: AsyncSession = Depends(get_db),
    _: User = _read,
):
    """List all configured Helm Repository instances."""
    service = HelmRepositoryInstanceService(db)
    return await service.list_instances()


@router.post(
    "/helm-repository",
    response_model=HelmRepositoryInstanceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_helm_repository_instance(
    data: HelmRepositoryInstanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _write,
):
    """Register a new Helm Repository instance."""
    service = HelmRepositoryInstanceService(db)
    try:
        result = await service.create_instance(
            name=data.name,
            url=data.url,
            username=data.username,
            password=data.password,
            is_active=data.is_active,
            verify_ssl=data.verify_ssl,
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


@router.get("/helm-repository/{instance_id}", response_model=HelmRepositoryInstanceOut)
async def get_helm_repository_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _read,
):
    """Get a single Helm Repository instance by ID."""
    service = HelmRepositoryInstanceService(db)
    try:
        return await service.get_instance(instance_id)
    except NotFoundError as e:
        raise e


@router.patch("/helm-repository/{instance_id}", response_model=HelmRepositoryInstanceOut)
async def update_helm_repository_instance(
    instance_id: int,
    data: HelmRepositoryInstanceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _write,
):
    """Update an existing Helm Repository instance (partial)."""
    service = HelmRepositoryInstanceService(db)
    try:
        result = await service.update_instance(
            instance_id=instance_id,
            name=data.name,
            url=data.url,
            username=data.username,
            password=data.password,
            is_active=data.is_active,
            verify_ssl=data.verify_ssl,
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


@router.delete("/helm-repository/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_helm_repository_instance(
    instance_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _write,
):
    """Delete a Helm Repository instance."""
    service = HelmRepositoryInstanceService(db)
    try:
        instance = await service.get_instance(instance_id)
        instance_name = instance.name
    except NotFoundError:
        instance_name = f"helm_repository_{instance_id}"

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


@router.post("/helm-repository/{instance_id}/test", response_model=ConnectionTestResult)
async def test_helm_repository_connection(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _write,
):
    """Test connectivity to a Helm Repository and update its status."""
    service = HelmRepositoryInstanceService(db)
    try:
        return await service.test_connection(instance_id)
    except NotFoundError as e:
        raise e
