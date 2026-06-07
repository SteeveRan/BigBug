"""
@file integrations/docker_registry.py
@description REST API for Docker Registry instance management.
@dependencies app.services.integrations (DockerRegistryInstanceService), app.core.rbac
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
    DockerRegistryInstanceCreate,
    DockerRegistryInstanceOut,
    DockerRegistryInstanceUpdate,
)
from app.services.audit import AuditService
from app.services.integrations import DockerRegistryInstanceService

router = APIRouter()
_manage = Depends(require_permission("docker_registry:manage"))


@router.get("/docker-registry", response_model=list[DockerRegistryInstanceOut])
async def list_docker_registry_instances(
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """List all configured Docker Registry instances."""
    service = DockerRegistryInstanceService(db)
    return await service.list_instances()


@router.post(
    "/docker-registry",
    response_model=DockerRegistryInstanceOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_docker_registry_instance(
    data: DockerRegistryInstanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _manage,
):
    """Register a new Docker Registry instance."""
    service = DockerRegistryInstanceService(db)
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


@router.get("/docker-registry/{instance_id}", response_model=DockerRegistryInstanceOut)
async def get_docker_registry_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Get a single Docker Registry instance by ID."""
    service = DockerRegistryInstanceService(db)
    try:
        return await service.get_instance(instance_id)
    except NotFoundError as e:
        raise e


@router.patch("/docker-registry/{instance_id}", response_model=DockerRegistryInstanceOut)
async def update_docker_registry_instance(
    instance_id: int,
    data: DockerRegistryInstanceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _manage,
):
    """Update an existing Docker Registry instance (partial)."""
    service = DockerRegistryInstanceService(db)
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


@router.delete("/docker-registry/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_docker_registry_instance(
    instance_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = _manage,
):
    """Delete a Docker Registry instance."""
    service = DockerRegistryInstanceService(db)
    try:
        instance = await service.get_instance(instance_id)
        instance_name = instance.name
    except NotFoundError:
        instance_name = f"docker_registry_{instance_id}"

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


@router.post("/docker-registry/{instance_id}/test", response_model=ConnectionTestResult)
async def test_docker_registry_connection(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Test connectivity to a Docker Registry and update its status."""
    service = DockerRegistryInstanceService(db)
    try:
        return await service.test_connection(instance_id)
    except NotFoundError as e:
        raise e
