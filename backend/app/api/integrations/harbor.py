"""
@file integrations/harbor.py
@description REST API for Harbor instance management.
@dependencies app.services.integrations (HarborInstanceService), app.core.rbac
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
    HarborInstanceCreate,
    HarborInstanceOut,
    HarborInstanceUpdate,
)
from app.services.audit import AuditService
from app.services.integrations import HarborInstanceService

router = APIRouter()
_manage = Depends(require_permission("integrations:manage"))


@router.get("/harbor", response_model=list[HarborInstanceOut])
async def list_harbor_instances(
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """List all configured Harbor instances."""
    service = HarborInstanceService(db)
    return await service.list_instances()


@router.post("/harbor", response_model=HarborInstanceOut, status_code=status.HTTP_201_CREATED)
async def create_harbor_instance(
    data: HarborInstanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _manage,
):
    """Register a new Harbor instance."""
    service = HarborInstanceService(db)
    try:
        result = await service.create_instance(
            name=data.name,
            url=data.url,
            username=data.username,
            password=data.password,
            is_active=data.is_active,
            verify_ssl=data.verify_ssl,
            is_default=data.is_default,
            default_project=data.default_project,
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


@router.get("/harbor/{instance_id}", response_model=HarborInstanceOut)
async def get_harbor_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Get a single Harbor instance by ID."""
    service = HarborInstanceService(db)
    try:
        return await service.get_instance(instance_id)
    except NotFoundError as e:
        raise e


@router.patch("/harbor/{instance_id}", response_model=HarborInstanceOut)
async def update_harbor_instance(
    instance_id: int,
    data: HarborInstanceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _manage,
):
    """Update an existing Harbor instance (partial)."""
    service = HarborInstanceService(db)
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
            default_project=data.default_project,
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


@router.delete("/harbor/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_harbor_instance(
    instance_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _manage,
):
    """Delete a Harbor instance."""
    service = HarborInstanceService(db)
    try:
        instance = await service.get_instance(instance_id)
        instance_name = instance.name
    except NotFoundError:
        instance_name = f"harbor_{instance_id}"

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


@router.post("/harbor/{instance_id}/test", response_model=ConnectionTestResult)
async def test_harbor_connection(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Test connectivity to a Harbor instance and update its status."""
    service = HarborInstanceService(db)
    try:
        return await service.test_connection(instance_id)
    except NotFoundError as e:
        raise e
