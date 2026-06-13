"""
@file mirroring.py
@description REST API for mirroring operations — source providers, source groups,
             source repositories, mirrors, and sync groups.
             Connects MirrorService, SyncGroupService, ReleaseService
             with permission-gated endpoints.
@dependencies app.services.mirror, app.services.sync_group, app.services.release,
              app.core.rbac, app.schemas.*
@relatedFiles ../services/mirror.py, ../services/sync_group.py, ../services/release.py,
              ../schemas/source_provider.py, ../schemas/source_group.py,
              ../schemas/source_repository.py, ../schemas/mirror.py,
              ../schemas/mirror_log.py, ../schemas/sync_group.py
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DomainError, NotFoundError
from app.core.rbac import get_current_user, require_permission, require_scope_permission
from app.database import get_db
from app.models.mirror import Mirror
from app.models.mirror_log import MirrorLogType
from app.models.source_group import SourceGroup
from app.models.source_provider import SourceProvider
from app.models.source_repository import SourceRepository
from app.models.user import User
from app.schemas.mirror import (
    IntegrityCheckResult,
    MirrorBulkCreate,
    MirrorCreate,
    MirrorDetailOut,
    MirrorListOut,
    MirrorUpdate,
)
from app.schemas.mirror_log import MirrorLogOut
from app.schemas.source_group import SourceGroupDetailOut, SourceGroupListOut
from app.schemas.source_provider import SourceProviderCreate, SourceProviderOut
from app.schemas.source_repository import (
    SourceRepositoryDetailOut,
    SourceRepositoryListOut,
    SourceRepositoryReadmeOut,
    SourceRepositoryReleaseOut,
)
from app.schemas.sync_group import (
    SyncGroupCreate,
    SyncGroupOut,
    SyncGroupUpdate,
)
from app.services.audit import AuditService
from app.services.mirror import MirrorService
from app.services.rbac_service import RBACService
from app.services.release import ReleaseService
from app.services.sync_group import SyncGroupService

logger = logging.getLogger(__name__)

router = APIRouter()


# ===================================================================
# Inline request schemas (no need for separate files)
# ===================================================================


class CheckDuplicatesRequest(BaseModel):
    """Request payload for duplicate mirror checking."""

    source_repo_ids: list[int]
    sync_group_id: int


class ImportMirrorRequest(BaseModel):
    """Request payload for importing an existing mirror."""

    source_repository_id: int
    target_namespace: str
    target_project_name: str


class AssignMirrorsRequest(BaseModel):
    """Request payload for bulk-assigning mirrors to a sync group."""

    mirror_ids: list[int] = Field(..., min_length=1, max_length=100)


class ApplyPipelineRequest(BaseModel):
    """Request payload for applying a Pipeline to a SyncGroup."""

    pipeline_id: int


class SourceProviderUpdate(BaseModel):
    """Partial update for a source provider — only label and credential."""

    credential_id: int | None = Field(None)
    label: str | None = Field(None, max_length=255)


# ===================================================================
# Source Providers  (5 endpoints)
# ===================================================================


@router.get("/providers/", response_model=list[SourceProviderOut])
async def list_source_providers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("source_groups:read")),
):
    """List all non-deleted source providers."""
    result = await db.execute(
        select(SourceProvider)
        .options(selectinload(SourceProvider.credential))
        .where(~SourceProvider.is_deleted)
        .order_by(SourceProvider.label.asc())
    )
    providers = result.unique().scalars().all()
    return [SourceProviderOut.model_validate(p) for p in providers]


@router.post("/providers/", response_model=SourceProviderOut, status_code=201)
async def create_source_provider(
    data: SourceProviderCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("source_groups:write")),
):
    """Create a new source provider (e.g. GitHub token connection)."""
    provider = SourceProvider(
        credential_id=data.credential_id,
        provider_type=data.provider_type,
        label=data.label,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    # Re-fetch with credential eager-loaded
    result = await db.execute(
        select(SourceProvider)
        .options(selectinload(SourceProvider.credential))
        .where(SourceProvider.id == provider.id)
    )
    provider = result.scalar_one()

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="source_provider.created",
        resource_type="source_provider",
        resource_id=provider.id,
        resource_name=provider.label,
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return SourceProviderOut.model_validate(provider)


@router.get("/providers/{provider_id}", response_model=SourceProviderOut)
async def get_source_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("source_groups:read")),
):
    """Get details of a single source provider."""
    result = await db.execute(
        select(SourceProvider)
        .options(selectinload(SourceProvider.credential))
        .where(SourceProvider.id == provider_id, ~SourceProvider.is_deleted)
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(
            status_code=404, detail=f"SourceProvider with id={provider_id} not found"
        )
    return SourceProviderOut.model_validate(provider)


@router.patch("/providers/{provider_id}", response_model=SourceProviderOut)
async def update_source_provider(
    provider_id: int,
    data: SourceProviderUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("source_groups:write")),
):
    """Partially update a source provider (label and/or credential)."""
    result = await db.execute(
        select(SourceProvider)
        .options(selectinload(SourceProvider.credential))
        .where(SourceProvider.id == provider_id, ~SourceProvider.is_deleted)
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(
            status_code=404, detail=f"SourceProvider with id={provider_id} not found"
        )

    changed = False
    if data.label is not None and data.label != provider.label:
        provider.label = data.label
        changed = True
    if data.credential_id is not None and data.credential_id != provider.credential_id:
        provider.credential_id = data.credential_id
        changed = True

    if changed:
        await db.commit()
        await db.refresh(provider)

    return SourceProviderOut.model_validate(provider)


@router.delete("/providers/{provider_id}", status_code=204)
async def delete_source_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("source_groups:write")),
):
    """Soft-delete a source provider."""
    result = await db.execute(
        select(SourceProvider).where(
            SourceProvider.id == provider_id,
            ~SourceProvider.is_deleted,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(
            status_code=404, detail=f"SourceProvider with id={provider_id} not found"
        )

    provider.is_deleted = True
    provider.deleted_at = datetime.now(UTC)

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="source_provider.deleted",
        resource_type="source_provider",
        resource_id=provider.id,
        resource_name=provider.name,
    )

    await db.commit()


@router.post("/providers/{provider_id}/restore", response_model=SourceProviderOut)
async def restore_source_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("source_groups:write")),
):
    """Restore a soft-deleted source provider."""
    result = await db.execute(select(SourceProvider).where(SourceProvider.id == provider_id))
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(
            status_code=404, detail=f"SourceProvider with id={provider_id} not found"
        )
    if not provider.is_deleted:
        raise HTTPException(status_code=400, detail="Source provider is not deleted")

    provider.is_deleted = False
    provider.deleted_at = None

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="source_provider.restored",
        resource_type="source_provider",
        resource_id=provider.id,
        resource_name=provider.name,
    )

    await db.commit()
    await db.refresh(provider)
    return SourceProviderOut.model_validate(provider)


# ===================================================================
# Source Groups — per provider  (5 endpoints)
# ===================================================================


@router.get("/providers/{provider_id}/groups/", response_model=list[SourceGroupListOut])
async def list_source_groups(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("source_groups:read")),
):
    """List all source groups for a given provider."""
    # Verify provider exists
    prov_result = await db.execute(
        select(SourceProvider).where(
            SourceProvider.id == provider_id,
            ~SourceProvider.is_deleted,
        )
    )
    if prov_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404, detail=f"SourceProvider with id={provider_id} not found"
        )

    result = await db.execute(
        select(SourceGroup)
        .options(
            selectinload(SourceGroup.source_provider),
            selectinload(SourceGroup.source_repositories),
        )
        .where(
            SourceGroup.source_provider_id == provider_id,
            ~SourceGroup.is_deleted,
        )
        .order_by(SourceGroup.name.asc())
    )
    groups = result.unique().scalars().all()
    return [SourceGroupListOut.model_validate(g) for g in groups]


@router.post(
    "/providers/{provider_id}/groups/import",
    response_model=SourceGroupDetailOut,
    status_code=201,
)
async def import_source_group(
    provider_id: int,
    request: Request,
    group_name: str = Query(..., description="GitHub organization or username"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("source_groups:write")),
):
    """Import an organization/group from GitHub and its repositories.

    Uses the SourceProvider's credential to fetch group metadata
    and all repositories via the configured SourceProvider.
    """
    # 1. Resolve provider + credential
    prov_result = await db.execute(
        select(SourceProvider)
        .options(selectinload(SourceProvider.credential))
        .where(
            SourceProvider.id == provider_id,
            ~SourceProvider.is_deleted,
        )
    )
    provider = prov_result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(
            status_code=404, detail=f"SourceProvider with id={provider_id} not found"
        )

    if provider.credential is None or not provider.credential.encrypted_secret:
        raise HTTPException(
            status_code=400,
            detail=f"SourceProvider {provider_id} has no credential configured",
        )

    from app.core.secrets import decrypt_secret
    from app.services.source_providers import create_source_provider

    credential_secret = decrypt_secret(provider.credential.encrypted_secret)
    gh_provider = await create_source_provider(provider, credential_secret)

    # 2. Find the group on GitHub
    github_groups = await gh_provider.list_groups()
    target_group = None
    for g in github_groups:
        if (
            g.get("name", "").lower() == group_name.lower()
            or g.get("login", "").lower() == group_name.lower()
        ):
            target_group = g
            break

    if target_group is None:
        raise HTTPException(
            status_code=404,
            detail=f"Group '{group_name}' not found on GitHub for provider {provider_id}",
        )

    external_id = (
        target_group.get("external_id") or target_group.get("login") or target_group.get("name")
    )

    # 3. Upsert SourceGroup
    existing_result = await db.execute(
        select(SourceGroup).where(
            SourceGroup.source_provider_id == provider_id,
            SourceGroup.external_id == external_id,
            ~SourceGroup.is_deleted,
        )
    )
    source_group = existing_result.scalar_one_or_none()

    if source_group is None:
        source_group = SourceGroup(
            source_provider_id=provider_id,
            external_id=external_id,
            name=target_group.get("name", group_name),
            full_path=target_group.get("full_name") or target_group.get("html_url"),
            web_url=target_group.get("html_url"),
            description=target_group.get("description"),
        )
        db.add(source_group)
        await db.flush()
        logger.info("Created SourceGroup id=%d name='%s'", source_group.id, source_group.name)
    else:
        logger.info(
            "SourceGroup id=%d name='%s' already exists", source_group.id, source_group.name
        )

    # 4. Import repositories
    repos = await gh_provider.list_repositories(external_id)
    imported_count = 0
    for repo in repos:
        repo_ext_id = repo.get("external_id") or repo.get("full_name")
        if not repo_ext_id:
            continue

        existing_repo = await db.execute(
            select(SourceRepository).where(
                SourceRepository.source_group_id == source_group.id,
                SourceRepository.external_id == repo_ext_id,
                ~SourceRepository.is_deleted,
            )
        )
        if existing_repo.scalar_one_or_none() is not None:
            continue

        repo_obj = SourceRepository(
            source_group_id=source_group.id,
            external_id=repo_ext_id,
            name=repo.get("name", ""),
            full_name=repo.get("full_name", ""),
            web_url=repo.get("html_url"),
            clone_url_https=repo.get("clone_url"),
            clone_url_ssh=repo.get("ssh_url"),
            description=repo.get("description"),
            default_branch=repo.get("default_branch"),
            license_spdx=repo.get("license_spdx"),
            license_name=repo.get("license_name"),
            is_archived=repo.get("archived", False),
            is_fork=repo.get("fork", False),
            is_disabled=repo.get("disabled", False),
            discovery_status="discovered",
            discovered_at=datetime.now(UTC),
            source_created_at=repo.get("created_at"),
            source_updated_at=repo.get("updated_at"),
            source_pushed_at=repo.get("pushed_at"),
        )
        db.add(repo_obj)
        imported_count += 1

    await db.commit()

    # 5. Re-fetch with relations
    result = await db.execute(
        select(SourceGroup)
        .options(
            selectinload(SourceGroup.source_provider).selectinload(SourceProvider.credential),
            selectinload(SourceGroup.source_repositories),
        )
        .where(SourceGroup.id == source_group.id)
    )
    source_group = result.unique().scalar_one()

    logger.info(
        "Import completed: group_id=%d, repos_imported=%d",
        source_group.id,
        imported_count,
    )

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="source_group.imported",
        resource_type="source_group",
        resource_id=source_group.id,
        resource_name=source_group.name,
        details={"repos_imported": imported_count},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return SourceGroupDetailOut.model_validate(source_group)


@router.get("/groups/{group_id}", response_model=SourceGroupDetailOut)
async def get_source_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_scope_permission("source_groups:read", "source_group", "group_id")),
):
    """Get details of a single source group with nested repositories."""
    result = await db.execute(
        select(SourceGroup)
        .options(
            selectinload(SourceGroup.source_provider).selectinload(SourceProvider.credential),
            selectinload(SourceGroup.source_repositories),
        )
        .where(SourceGroup.id == group_id, ~SourceGroup.is_deleted)
    )
    group = result.unique().scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail=f"SourceGroup with id={group_id} not found")
    return SourceGroupDetailOut.model_validate(group)


@router.post("/groups/{group_id}/refresh", response_model=SourceGroupDetailOut)
async def refresh_source_group(
    group_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(
        require_scope_permission("source_groups:refresh", "source_group", "group_id")
    ),
):
    """Re-fetch repository list for a source group from the upstream provider."""
    # Get group with provider + credential
    result = await db.execute(
        select(SourceGroup)
        .options(
            selectinload(SourceGroup.source_provider).selectinload(SourceProvider.credential),
            selectinload(SourceGroup.source_repositories),
        )
        .where(SourceGroup.id == group_id, ~SourceGroup.is_deleted)
    )
    group = result.unique().scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail=f"SourceGroup with id={group_id} not found")

    if group.source_provider is None:
        raise HTTPException(status_code=400, detail="SourceGroup has no linked SourceProvider")

    sp = group.source_provider
    if sp.credential is None or not sp.credential.encrypted_secret:
        raise HTTPException(status_code=400, detail="SourceProvider has no credential configured")

    from app.core.secrets import decrypt_secret
    from app.services.source_providers import create_source_provider

    credential_secret = decrypt_secret(sp.credential.encrypted_secret)
    gh_provider = await create_source_provider(sp, credential_secret)

    external_id = group.external_id or group.name
    repos = await gh_provider.list_repositories(external_id)

    imported_count = 0
    for repo in repos:
        repo_ext_id = repo.get("external_id") or repo.get("full_name")
        if not repo_ext_id:
            continue

        existing_repo = await db.execute(
            select(SourceRepository).where(
                SourceRepository.source_group_id == group.id,
                SourceRepository.external_id == repo_ext_id,
                ~SourceRepository.is_deleted,
            )
        )
        sr = existing_repo.scalar_one_or_none()
        if sr is not None:
            # Update last_seen_at and other mutable fields
            sr.last_seen_at = datetime.now(UTC)
            sr.is_archived = repo.get("archived", False)
            sr.is_disabled = repo.get("disabled", False)
            sr.source_pushed_at = repo.get("pushed_at")
            sr.source_updated_at = repo.get("updated_at")
            continue

        sr = SourceRepository(
            source_group_id=group.id,
            external_id=repo_ext_id,
            name=repo.get("name", ""),
            full_name=repo.get("full_name", ""),
            web_url=repo.get("html_url"),
            clone_url_https=repo.get("clone_url"),
            clone_url_ssh=repo.get("ssh_url"),
            description=repo.get("description"),
            default_branch=repo.get("default_branch"),
            license_spdx=repo.get("license_spdx"),
            license_name=repo.get("license_name"),
            is_archived=repo.get("archived", False),
            is_fork=repo.get("fork", False),
            is_disabled=repo.get("disabled", False),
            discovery_status="discovered",
            discovered_at=datetime.now(UTC),
            source_created_at=repo.get("created_at"),
            source_updated_at=repo.get("updated_at"),
            source_pushed_at=repo.get("pushed_at"),
        )
        db.add(sr)
        imported_count += 1

    await db.commit()

    # Re-fetch
    result = await db.execute(
        select(SourceGroup)
        .options(
            selectinload(SourceGroup.source_provider).selectinload(SourceProvider.credential),
            selectinload(SourceGroup.source_repositories),
        )
        .where(SourceGroup.id == group.id)
    )
    group = result.unique().scalar_one()

    logger.info(
        "Refresh completed: group_id=%d, new_repos=%d",
        group.id,
        imported_count,
    )

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="source_group.refreshed",
        resource_type="source_group",
        resource_id=group.id,
        resource_name=group.name,
        details={"new_repos": imported_count},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()

    return SourceGroupDetailOut.model_validate(group)


@router.delete("/groups/{group_id}", status_code=204)
async def delete_source_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("source_groups:write", "source_group", "group_id")),
):
    """Soft-delete a source group."""
    result = await db.execute(
        select(SourceGroup).where(
            SourceGroup.id == group_id,
            ~SourceGroup.is_deleted,
        )
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail=f"SourceGroup with id={group_id} not found")

    group.is_deleted = True
    group.deleted_at = datetime.now(UTC)

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="source_group.deleted",
        resource_type="source_group",
        resource_id=group.id,
        resource_name=group.name,
    )

    await db.commit()


@router.post("/groups/{group_id}/restore", response_model=SourceGroupDetailOut)
async def restore_source_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("source_groups:write", "source_group", "group_id")),
):
    """Restore a soft-deleted source group."""
    result = await db.execute(
        select(SourceGroup)
        .options(selectinload(SourceGroup.repositories))
        .where(SourceGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail=f"SourceGroup with id={group_id} not found")
    if not group.is_deleted:
        raise HTTPException(status_code=400, detail="Source group is not deleted")

    group.is_deleted = False
    group.deleted_at = None

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="source_group.restored",
        resource_type="source_group",
        resource_id=group.id,
        resource_name=group.name,
    )

    await db.commit()
    await db.refresh(group)
    return SourceGroupDetailOut.model_validate(group)


# ===================================================================
# Source Repositories  (4 endpoints)
# ===================================================================


@router.get("/groups/{group_id}/repositories/", response_model=list[SourceRepositoryListOut])
async def list_source_repositories(
    group_id: int,
    discovery_status: str | None = Query(None, description="Filter by discovery_status"),
    is_archived: bool | None = Query(None, description="Filter archived repos"),
    search: str | None = Query(None, description="Search by name or full_name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_scope_permission("source_groups:read", "source_group", "group_id")),
):
    """List repositories in a source group with optional filtering."""
    # Verify group exists
    grp_result = await db.execute(
        select(SourceGroup).where(
            SourceGroup.id == group_id,
            ~SourceGroup.is_deleted,
        )
    )
    if grp_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"SourceGroup with id={group_id} not found")

    query = (
        select(SourceRepository)
        .options(selectinload(SourceRepository.source_group))
        .where(
            SourceRepository.source_group_id == group_id,
            ~SourceRepository.is_deleted,
        )
    )

    if discovery_status is not None:
        query = query.where(SourceRepository.discovery_status == discovery_status)
    if is_archived is not None:
        query = query.where(SourceRepository.is_archived == is_archived)
    if search:
        search_term = f"%{search}%"
        query = query.where(SourceRepository.full_name.ilike(search_term))

    query = query.order_by(SourceRepository.name.asc()).offset(offset).limit(limit)

    result = await db.execute(query)
    repos = result.scalars().all()
    return [SourceRepositoryListOut.model_validate(r) for r in repos]


@router.get("/repositories/{repository_id}", response_model=SourceRepositoryDetailOut)
async def get_source_repository(
    repository_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:read")),
):
    """Get details of a single source repository."""

    result = await db.execute(
        select(SourceRepository)
        .options(
            selectinload(SourceRepository.source_group).selectinload(SourceGroup.source_provider),
            selectinload(SourceRepository.mirrors),
        )
        .where(SourceRepository.id == repository_id, ~SourceRepository.is_deleted)
    )
    repo = result.unique().scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=404, detail=f"SourceRepository with id={repository_id} not found"
        )
    # Scope check via parent SourceGroup
    rbac = RBACService(db)
    if not await rbac.check_scope_access(current_user.id, "source_group", repo.source_group_id):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )
    return SourceRepositoryDetailOut.model_validate(repo)


@router.get(
    "/repositories/{repository_id}/releases/", response_model=list[SourceRepositoryReleaseOut]
)
async def get_repository_releases(
    repository_id: int,
    include_prereleases: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:read")),
):
    """List tracked releases for a source repository."""
    # Scope check via parent SourceGroup
    repo_result = await db.execute(
        select(SourceRepository).where(
            SourceRepository.id == repository_id,
            ~SourceRepository.is_deleted,
        )
    )
    repo = repo_result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=404, detail=f"SourceRepository with id={repository_id} not found"
        )
    rbac = RBACService(db)
    if not await rbac.check_scope_access(current_user.id, "source_group", repo.source_group_id):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    releases = await ReleaseService.get_releases(
        db,
        repository_id=repository_id,
        include_prereleases=include_prereleases,
    )
    return [SourceRepositoryReleaseOut.model_validate(r) for r in releases]


@router.get("/repositories/{repository_id}/readme", response_model=SourceRepositoryReadmeOut)
async def get_repository_readme(
    repository_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:read")),
):
    """Get cached README content for a source repository."""
    result = await db.execute(
        select(SourceRepository).where(
            SourceRepository.id == repository_id,
            ~SourceRepository.is_deleted,
        )
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=404, detail=f"SourceRepository with id={repository_id} not found"
        )
    # Scope check via parent SourceGroup
    rbac = RBACService(db)
    if not await rbac.check_scope_access(current_user.id, "source_group", repo.source_group_id):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )
    return SourceRepositoryReadmeOut(
        readme_html=repo.readme_html,
        readme_fetched_at=repo.readme_fetched_at,
    )


@router.delete("/repositories/{repository_id}", status_code=204)
async def delete_source_repository(
    repository_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:write")),
):
    """Soft-delete a source repository (only if not referenced by active mirrors)."""
    result = await db.execute(
        select(SourceRepository)
        .options(selectinload(SourceRepository.mirrors))
        .where(SourceRepository.id == repository_id, ~SourceRepository.is_deleted)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=404, detail=f"SourceRepository with id={repository_id} not found"
        )
    # Scope check via parent SourceGroup
    rbac = RBACService(db)
    if not await rbac.check_scope_access(current_user.id, "source_group", repo.source_group_id):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    # Check for active mirrors referencing this repository
    active_mirrors = [m for m in repo.mirrors if not m.is_deleted]
    if active_mirrors:
        mirror_ids = [m.id for m in active_mirrors]
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: active mirrors still reference this repository: {mirror_ids}",
        )

    repo.is_deleted = True
    repo.deleted_at = datetime.now(UTC)

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="source_repository.deleted",
        resource_type="source_repository",
        resource_id=repo.id,
        resource_name=repo.full_name,
    )

    await db.commit()


@router.post("/repositories/{repository_id}/restore", response_model=SourceRepositoryDetailOut)
async def restore_source_repository(
    repository_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:write")),
):
    """Restore a soft-deleted source repository."""
    result = await db.execute(
        select(SourceRepository)
        .options(
            selectinload(SourceRepository.source_group).selectinload(SourceGroup.source_provider),
            selectinload(SourceRepository.mirrors),
        )
        .where(SourceRepository.id == repository_id)
    )
    repo = result.unique().scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=404, detail=f"SourceRepository with id={repository_id} not found"
        )
    if not repo.is_deleted:
        raise HTTPException(status_code=400, detail="Source repository is not deleted")
    # Scope check via parent SourceGroup
    rbac = RBACService(db)
    if not await rbac.check_scope_access(current_user.id, "source_group", repo.source_group_id):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    repo.is_deleted = False
    repo.deleted_at = None

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="source_repository.restored",
        resource_type="source_repository",
        resource_id=repo.id,
        resource_name=repo.full_name,
    )

    await db.commit()
    await db.refresh(repo)
    return SourceRepositoryDetailOut.model_validate(repo)


# ===================================================================
# Mirrors  (11 endpoints)
# ===================================================================


@router.get("/mirrors/", response_model=list[MirrorListOut])
async def list_mirrors(
    source_group_id: int | None = Query(None),
    sync_group_id: int | None = Query(None),
    status_flag: int | None = Query(None, ge=0, le=4),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at", pattern="^(source_url|created_at|updated_at|last_sync_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("mirrors:read")),
):
    """List mirrors with RBAC-scoped filtering."""
    filters: dict = {}
    if source_group_id is not None:
        filters["source_group_id"] = source_group_id
    if sync_group_id is not None:
        filters["sync_group_id"] = sync_group_id
    if status_flag is not None:
        filters["status_flag"] = status_flag
    if search:
        filters["search"] = search

    items, _total = await MirrorService.list_mirrors(
        db,
        filters=filters if filters else None,
        user=current_user,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return [MirrorListOut.model_validate(m) for m in items]


@router.get("/mirrors/{mirror_id}", response_model=MirrorDetailOut)
async def get_mirror(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:read")),
):
    """Get mirror details with relationships and recent logs."""
    try:
        mirror = await MirrorService.get_mirror_detail(db, mirror_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from e
    # Scope check via parent SyncGroup
    rbac = RBACService(db)
    if not await rbac.check_scope_access(current_user.id, "sync_group", mirror.sync_group_id):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )
    return MirrorDetailOut.model_validate(mirror)


@router.post("/mirrors/", response_model=MirrorDetailOut, status_code=201)
async def create_mirror(
    data: MirrorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("mirrors:write")),
):
    """Create a single mirror for a source repository."""
    try:
        mirror = await MirrorService.create_mirror(
            db,
            data=data,
            user_id=current_user.id,
            username=current_user.username,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return MirrorDetailOut.model_validate(mirror)


@router.post("/mirrors/bulk", response_model=list[MirrorListOut], status_code=201)
async def bulk_create_mirrors(
    data: MirrorBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("mirrors:write")),
):
    """Create multiple mirrors in a single batch operation."""
    try:
        mirrors = await MirrorService.bulk_create_mirrors(
            db,
            data=data,
            user_id=current_user.id,
            username=current_user.username,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return [MirrorListOut.model_validate(m) for m in mirrors]


@router.patch("/mirrors/{mirror_id}", response_model=MirrorDetailOut)
async def update_mirror(
    mirror_id: int,
    data: MirrorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:write")),
):
    """Partially update a mirror's target fields."""
    # Scope check via parent SyncGroup
    result = await db.execute(select(Mirror).where(Mirror.id == mirror_id, ~Mirror.is_deleted))
    mirror_for_scope = result.scalar_one_or_none()
    if mirror_for_scope is None:
        raise HTTPException(status_code=404, detail=f"Mirror with id={mirror_id} not found")
    rbac = RBACService(db)
    if not await rbac.check_scope_access(
        current_user.id, "sync_group", mirror_for_scope.sync_group_id
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    try:
        mirror = await MirrorService.update_mirror(
            db,
            mirror_id=mirror_id,
            data=data,
            username=current_user.username,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return MirrorDetailOut.model_validate(mirror)


@router.delete("/mirrors/{mirror_id}", status_code=204)
async def delete_mirror(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:delete")),
):
    """Soft-delete a mirror."""
    # Scope check via parent SyncGroup
    result = await db.execute(select(Mirror).where(Mirror.id == mirror_id, ~Mirror.is_deleted))
    mirror_for_scope = result.scalar_one_or_none()
    if mirror_for_scope is None:
        raise HTTPException(status_code=404, detail=f"Mirror with id={mirror_id} not found")
    rbac = RBACService(db)
    if not await rbac.check_scope_access(
        current_user.id, "sync_group", mirror_for_scope.sync_group_id
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    try:
        await MirrorService.soft_delete_mirror(
            db,
            mirror_id=mirror_id,
            username=current_user.username,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from e


@router.post("/mirrors/{mirror_id}/restore", response_model=MirrorDetailOut)
async def restore_mirror(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:delete")),
):
    """Restore a soft-deleted mirror."""
    # Scope check via parent SyncGroup — find mirror INCLUDING soft-deleted
    result = await db.execute(select(Mirror).where(Mirror.id == mirror_id))
    mirror_for_scope = result.scalar_one_or_none()
    if mirror_for_scope is None:
        raise HTTPException(status_code=404, detail=f"Mirror with id={mirror_id} not found")
    rbac = RBACService(db)
    if not await rbac.check_scope_access(
        current_user.id, "sync_group", mirror_for_scope.sync_group_id
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    try:
        mirror = await MirrorService.restore_mirror(
            db,
            mirror_id=mirror_id,
            username=current_user.username,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from e

    return MirrorDetailOut.model_validate(mirror)


@router.post("/mirrors/{mirror_id}/sync", response_model=MirrorLogOut, status_code=201)
async def trigger_mirror_sync(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:sync")),
):
    """Trigger a sync pipeline for a mirror."""
    # Scope check via parent SyncGroup
    result = await db.execute(select(Mirror).where(Mirror.id == mirror_id, ~Mirror.is_deleted))
    mirror_for_scope = result.scalar_one_or_none()
    if mirror_for_scope is None:
        raise HTTPException(status_code=404, detail=f"Mirror with id={mirror_id} not found")
    rbac = RBACService(db)
    if not await rbac.check_scope_access(
        current_user.id, "sync_group", mirror_for_scope.sync_group_id
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    try:
        mirror_log = await MirrorService.trigger_sync(
            db,
            mirror_id=mirror_id,
            user_id=current_user.id,
            username=current_user.username,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return MirrorLogOut.model_validate(mirror_log)


@router.post("/mirrors/{mirror_id}/freshness", response_model=MirrorLogOut, status_code=201)
async def check_mirror_freshness(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:sync")),
):
    """Run a freshness check comparing source HEAD against last known commit."""
    # Scope check via parent SyncGroup
    result = await db.execute(select(Mirror).where(Mirror.id == mirror_id, ~Mirror.is_deleted))
    mirror_for_scope = result.scalar_one_or_none()
    if mirror_for_scope is None:
        raise HTTPException(status_code=404, detail=f"Mirror with id={mirror_id} not found")
    rbac = RBACService(db)
    if not await rbac.check_scope_access(
        current_user.id, "sync_group", mirror_for_scope.sync_group_id
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    try:
        mirror_log = await MirrorService.check_freshness(
            db,
            mirror_id=mirror_id,
            username=current_user.username,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return MirrorLogOut.model_validate(mirror_log)


@router.post("/mirrors/import", response_model=MirrorDetailOut, status_code=201)
async def import_mirror(
    data: ImportMirrorRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("mirrors:import")),
):
    """Import (register) an existing mirror for a source repository."""
    try:
        mirror = await MirrorService.create_mirror(
            db,
            data=MirrorCreate(
                source_repository_id=data.source_repository_id,
                target_namespace=data.target_namespace,
                target_project_name=data.target_project_name,
            ),
            user_id=current_user.id,
            username=current_user.username,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    # Re-fetch with eager-loaded relations
    mirror = await MirrorService.get_mirror_detail(db, mirror.id)
    return MirrorDetailOut.model_validate(mirror)


@router.post("/mirrors/check-duplicates", response_model=dict)
async def check_mirror_duplicates(
    data: CheckDuplicatesRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mirrors:write")),
):
    """Check for duplicate mirrors across sync groups."""
    result = await MirrorService.check_duplicates(
        db,
        source_repo_ids=data.source_repo_ids,
        sync_group_id=data.sync_group_id,
    )
    return result


@router.get("/mirrors/{mirror_id}/logs/", response_model=list[MirrorLogOut])
async def get_mirror_logs(
    mirror_id: int,
    log_type: MirrorLogType | None = Query(None, description="Filter by log type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:read")),
):
    """List log entries for a mirror with optional type filter."""
    # Verify mirror exists + scope check via parent SyncGroup
    mirror_result = await db.execute(
        select(Mirror).where(Mirror.id == mirror_id, ~Mirror.is_deleted)
    )
    mirror_for_scope = mirror_result.scalar_one_or_none()
    if mirror_for_scope is None:
        raise HTTPException(status_code=404, detail=f"Mirror with id={mirror_id} not found")
    rbac = RBACService(db)
    if not await rbac.check_scope_access(
        current_user.id, "sync_group", mirror_for_scope.sync_group_id
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    logs = await MirrorService.get_logs(
        db,
        mirror_id=mirror_id,
        log_type=log_type,
        limit=limit,
        offset=offset,
    )
    return [MirrorLogOut.model_validate(log) for log in logs]


# ===================================================================
# Sync Groups  (6 endpoints)
# ===================================================================


@router.get("/sync-groups/", response_model=list[SyncGroupOut])
async def list_sync_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sync_groups:read")),
):
    """List all sync groups with RBAC-scoped filtering."""
    groups = await SyncGroupService.get_sync_groups(db, user=current_user)
    return [SyncGroupOut.model_validate(g) for g in groups]


@router.post("/sync-groups/", response_model=SyncGroupOut, status_code=201)
async def create_sync_group(
    data: SyncGroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sync_groups:write")),
):
    """Create a new sync group."""
    try:
        group = await SyncGroupService.create_sync_group(
            db,
            data=data,
            user_id=current_user.id,
            username=current_user.username,
        )
    except DomainError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    return SyncGroupOut.model_validate(group)


@router.get("/sync-groups/{group_id}", response_model=SyncGroupOut)
async def get_sync_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_scope_permission("sync_groups:read", "sync_group", "group_id")),
):
    """Get details of a single sync group."""
    try:
        group = await SyncGroupService.get_sync_group(db, group_id)
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return SyncGroupOut.model_validate(group)


@router.patch("/sync-groups/{group_id}", response_model=SyncGroupOut)
async def update_sync_group(
    group_id: int,
    data: SyncGroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("sync_groups:write", "sync_group", "group_id")),
):
    """Partially update a sync group."""
    try:
        group = await SyncGroupService.update_sync_group(
            db,
            group_id=group_id,
            data=data,
            username=current_user.username,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return SyncGroupOut.model_validate(group)


@router.delete("/sync-groups/{group_id}", status_code=204)
async def delete_sync_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_scope_permission("sync_groups:delete", "sync_group", "group_id")),
):
    """Soft-delete a sync group (mirrors are migrated to default group)."""
    try:
        await SyncGroupService.delete_sync_group(db, group_id)
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e


@router.post("/sync-groups/{group_id}/restore", response_model=SyncGroupOut)
async def restore_sync_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("sync_groups:delete", "sync_group", "group_id")),
):
    """Restore a soft-deleted sync group."""
    try:
        group = await SyncGroupService.restore_sync_group(
            db,
            group_id=group_id,
            user_id=current_user.id,
            username=current_user.username,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return SyncGroupOut.model_validate(group)


@router.post(
    "/sync-groups/{group_id}/mirrors/bulk",
    response_model=SyncGroupOut,
)
async def bulk_assign_mirrors_to_group(
    group_id: int,
    data: AssignMirrorsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("sync_groups:write", "sync_group", "group_id")),
):
    """Bulk assign mirrors to a SyncGroup.

    Validates that all mirror IDs exist. Mirrors already in the group are
    skipped (idempotent). Mirrors from other groups are moved to this group.
    """
    try:
        group = await SyncGroupService.bulk_assign_mirrors(
            db,
            sync_group_id=group_id,
            mirror_ids=data.mirror_ids,
            user_id=current_user.id,
            username=current_user.username,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return SyncGroupOut.model_validate(group)


# ────────────────────────────────────────────────────────────────────────────
# Integrity Check (direct, no CI/CD pipeline)
# ────────────────────────────────────────────────────────────────────────────


@router.post(
    "/mirrors/{mirror_id}/integrity-check",
    response_model=IntegrityCheckResult,
)
async def check_mirror_integrity(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IntegrityCheckResult:
    """Compare source HEAD commit against target GitLab project directly.

    Does NOT trigger a CI/CD pipeline — fetches commits from both sides
    and returns a comparison result (MATCH / MISMATCH / ERROR).
    """
    try:
        result = await MirrorService.check_integrity_direct(
            db,
            mirror_id=mirror_id,
            username=current_user.username,
        )
        return IntegrityCheckResult(
            mirror_id=result.mirror_id,
            status=result.status,
            source_commit_sha=result.source_commit_sha,
            target_commit_sha=result.target_commit_sha,
            message=result.message,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e


@router.post(
    "/sync-groups/{group_id}/apply-pipeline",
    response_model=SyncGroupOut,
)
async def apply_pipeline_to_sync_group(
    group_id: int,
    request: ApplyPipelineRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("sync_groups:write", "sync_group", "group_id")),
):
    """Apply a Pipeline configuration to a SyncGroup.

    Updates the pipeline_id on the sync group so all mirrors in that
    group use the specified pipeline for future sync operations.
    """
    try:
        group = await SyncGroupService.apply_pipeline(
            db,
            sync_group_id=group_id,
            pipeline_id=request.pipeline_id,
            user_id=current_user.id,
            username=current_user.username,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return SyncGroupOut.model_validate(group)
