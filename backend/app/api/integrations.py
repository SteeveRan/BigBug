"""
@file integrations.py
@description REST API for managing multiple integration instances:
             GitLab, Harbor, GitHub. All endpoints require
             ``integrations:manage`` permission.
@dependencies app.services.integrations (GitlabInstanceService,
              HarborInstanceService, GithubInstanceService),
              app.core.rbac (require_permission), app.schemas.integrations
@relatedFiles ../services/integrations.py, ../schemas/integrations.py
"""

from fastapi import APIRouter, Depends, status
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
    GithubInstanceCreate,
    GithubInstanceOut,
    GithubInstanceUpdate,
    GitlabInstanceCreate,
    GitlabInstanceOut,
    GitlabInstanceUpdate,
    HarborInstanceCreate,
    HarborInstanceOut,
    HarborInstanceUpdate,
    HelmRepositoryInstanceCreate,
    HelmRepositoryInstanceOut,
    HelmRepositoryInstanceUpdate,
)
from app.services.integrations import (
    DockerRegistryInstanceService,
    GithubInstanceService,
    GitlabInstanceService,
    HarborInstanceService,
    HelmRepositoryInstanceService,
)

router = APIRouter()

# Permission dependencies
_manage = Depends(require_permission("integrations:manage"))
_manage_docker_registry = Depends(require_permission("docker_registry:manage"))
_manage_helm_repository = Depends(require_permission("helm_repository:manage"))


# ===================================================================
# GitLab Instances
# ===================================================================


@router.get("/gitlab", response_model=list[GitlabInstanceOut])
async def list_gitlab_instances(
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """List all configured GitLab instances."""
    service = GitlabInstanceService(db)
    return await service.list_instances()


@router.post("/gitlab", response_model=GitlabInstanceOut, status_code=status.HTTP_201_CREATED)
async def create_gitlab_instance(
    data: GitlabInstanceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Register a new GitLab instance."""
    service = GitlabInstanceService(db)
    try:
        return await service.create_instance(
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


@router.get("/gitlab/{instance_id}", response_model=GitlabInstanceOut)
async def get_gitlab_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
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
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Update an existing GitLab instance (partial)."""
    service = GitlabInstanceService(db)
    try:
        return await service.update_instance(
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


@router.delete("/gitlab/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gitlab_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Delete a GitLab instance."""
    service = GitlabInstanceService(db)
    try:
        await service.delete_instance(instance_id)
    except NotFoundError as e:
        raise e


@router.post("/gitlab/{instance_id}/test", response_model=ConnectionTestResult)
async def test_gitlab_connection(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Test connectivity to a GitLab instance and update its status."""
    service = GitlabInstanceService(db)
    try:
        return await service.test_connection(instance_id)
    except NotFoundError as e:
        raise e


# ===================================================================
# Harbor Instances
# ===================================================================


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
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Register a new Harbor instance."""
    service = HarborInstanceService(db)
    try:
        return await service.create_instance(
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
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Update an existing Harbor instance (partial)."""
    service = HarborInstanceService(db)
    try:
        return await service.update_instance(
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


@router.delete("/harbor/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_harbor_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Delete a Harbor instance."""
    service = HarborInstanceService(db)
    try:
        await service.delete_instance(instance_id)
    except NotFoundError as e:
        raise e


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


# ===================================================================
# GitHub Instances
# ===================================================================


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
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Register a new GitHub instance (token)."""
    service = GithubInstanceService(db)
    try:
        return await service.create_instance(
            name=data.name,
            token=data.token,
            is_active=data.is_active,
            is_default=data.is_default,
        )
    except ConflictError as e:
        raise e


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
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Update an existing GitHub instance (partial)."""
    service = GithubInstanceService(db)
    try:
        return await service.update_instance(
            instance_id=instance_id,
            name=data.name,
            token=data.token,
            is_active=data.is_active,
            is_default=data.is_default,
        )
    except (NotFoundError, ConflictError) as e:
        raise e


@router.delete("/github/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_github_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage,
):
    """Delete a GitHub instance."""
    service = GithubInstanceService(db)
    try:
        await service.delete_instance(instance_id)
    except NotFoundError as e:
        raise e


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


# ===================================================================
# Docker Registry Instances
# ===================================================================


@router.get("/docker-registry", response_model=list[DockerRegistryInstanceOut])
async def list_docker_registry_instances(
    db: AsyncSession = Depends(get_db),
    _: User = _manage_docker_registry,
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
    db: AsyncSession = Depends(get_db),
    _: User = _manage_docker_registry,
):
    """Register a new Docker Registry instance."""
    service = DockerRegistryInstanceService(db)
    try:
        return await service.create_instance(
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


@router.get("/docker-registry/{instance_id}", response_model=DockerRegistryInstanceOut)
async def get_docker_registry_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage_docker_registry,
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
    db: AsyncSession = Depends(get_db),
    _: User = _manage_docker_registry,
):
    """Update an existing Docker Registry instance (partial)."""
    service = DockerRegistryInstanceService(db)
    try:
        return await service.update_instance(
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


@router.delete("/docker-registry/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_docker_registry_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage_docker_registry,
):
    """Delete a Docker Registry instance."""
    service = DockerRegistryInstanceService(db)
    try:
        await service.delete_instance(instance_id)
    except NotFoundError as e:
        raise e


@router.post("/docker-registry/{instance_id}/test", response_model=ConnectionTestResult)
async def test_docker_registry_connection(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage_docker_registry,
):
    """Test connectivity to a Docker Registry and update its status."""
    service = DockerRegistryInstanceService(db)
    try:
        return await service.test_connection(instance_id)
    except NotFoundError as e:
        raise e


# ===================================================================
# Helm Repository Instances
# ===================================================================


@router.get("/helm-repository", response_model=list[HelmRepositoryInstanceOut])
async def list_helm_repository_instances(
    db: AsyncSession = Depends(get_db),
    _: User = _manage_helm_repository,
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
    db: AsyncSession = Depends(get_db),
    _: User = _manage_helm_repository,
):
    """Register a new Helm Repository instance."""
    service = HelmRepositoryInstanceService(db)
    try:
        return await service.create_instance(
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


@router.get("/helm-repository/{instance_id}", response_model=HelmRepositoryInstanceOut)
async def get_helm_repository_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage_helm_repository,
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
    db: AsyncSession = Depends(get_db),
    _: User = _manage_helm_repository,
):
    """Update an existing Helm Repository instance (partial)."""
    service = HelmRepositoryInstanceService(db)
    try:
        return await service.update_instance(
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


@router.delete("/helm-repository/{instance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_helm_repository_instance(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage_helm_repository,
):
    """Delete a Helm Repository instance."""
    service = HelmRepositoryInstanceService(db)
    try:
        await service.delete_instance(instance_id)
    except NotFoundError as e:
        raise e


@router.post("/helm-repository/{instance_id}/test", response_model=ConnectionTestResult)
async def test_helm_repository_connection(
    instance_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = _manage_helm_repository,
):
    """Test connectivity to a Helm Repository and update its status."""
    service = HelmRepositoryInstanceService(db)
    try:
        return await service.test_connection(instance_id)
    except NotFoundError as e:
        raise e
