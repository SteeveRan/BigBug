"""
@file mirroring.py
@description REST API for mirroring operations — source groups, source
             repositories, mirrors, and sync groups. Thin transport layer:
             business logic lives in SourceGroupService, SourceRepositoryService,
             MirrorService, SyncGroupService, ReleaseService (phase 7E, Providers V3:
             the provider part moved to /api/providers; git providers are resolved
             from resource_providers only).
@dependencies app.services.source_group, app.services.source_repository,
              app.services.mirror, app.services.sync_group, app.services.release,
              app.core.rbac, app.schemas.*
@relatedFiles ../services/source_group.py, ../services/source_repository.py,
              ../services/mirror.py, ../services/sync_group.py, ../services/release.py
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import get_current_user, require_permission, require_scope_permission
from app.database import get_db
from app.models.mirror import Mirror
from app.models.mirror_log import MirrorLogType
from app.models.resource_provider import ResourceProvider
from app.models.source_group import SourceGroup
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
from app.schemas.source_repository import (
    SourceRepositoryCreate,
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
from app.services.source_group import SourceGroupService
from app.services.source_repository import (
    SourceRepositoryService,
    fetch_metadata_background,
)
from app.services.sync_group import SyncGroupService

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


# ===================================================================
# Scope-check helpers (RBAC stays in the transport layer)
# ===================================================================


async def _check_sync_group_scope(
    db: AsyncSession, current_user: User, mirror_id: int, *, include_deleted: bool = False
) -> None:
    """Verify the mirror exists and its SyncGroup is in the user's scope."""
    query = select(Mirror).where(Mirror.id == mirror_id)
    if not include_deleted:
        query = query.where(~Mirror.is_deleted)
    result = await db.execute(query)
    mirror = result.scalar_one_or_none()
    if mirror is None:
        raise HTTPException(status_code=404, detail=f"Mirror with id={mirror_id} not found")
    rbac = RBACService(db)
    if not await rbac.check_scope_access(current_user.id, "sync_group", mirror.sync_group_id):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )


async def _get_scoped_repository(
    db: AsyncSession, current_user: User, repository_id: int, *, include_deleted: bool = False
) -> SourceRepository:
    """Fetch a repository and verify scope via its parent SourceGroup."""
    query = select(SourceRepository).where(SourceRepository.id == repository_id)
    if not include_deleted:
        query = query.where(~SourceRepository.is_deleted)
    result = await db.execute(query)
    repo = result.scalar_one_or_none()
    if repo is None:
        raise HTTPException(
            status_code=404, detail=f"SourceRepository with id={repository_id} not found"
        )
    if repo.source_group_id is not None:
        rbac = RBACService(db)
        if not await rbac.check_scope_access(current_user.id, "source_group", repo.source_group_id):
            raise HTTPException(
                status_code=403, detail="Access denied: resource not in your role scope"
            )
    return repo


# ===================================================================
# Source Groups — per provider
# ===================================================================


@router.get("/groups", response_model=list[SourceGroupListOut])
async def list_source_groups(
    provider_id: int | None = Query(None, description="Filter groups by resource provider"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("source_groups:read")),
):
    """List all source groups, optionally filtered by resource provider."""
    query = (
        select(SourceGroup)
        .options(selectinload(SourceGroup.source_repositories))
        .where(~SourceGroup.is_deleted)
    )

    if provider_id is not None:
        # Filter groups that have at least one repository linked to this provider
        query = (
            select(SourceGroup)
            .distinct()
            .join(
                SourceRepository,
                SourceRepository.source_group_id == SourceGroup.id,
            )
            .options(selectinload(SourceGroup.source_repositories))
            .where(
                SourceRepository.provider_id == provider_id,
                ~SourceGroup.is_deleted,
            )
        )

    query = query.order_by(SourceGroup.name.asc())
    result = await db.execute(query)
    groups = result.unique().scalars().all()
    return [SourceGroupListOut.model_validate(g) for g in groups]


@router.post("/groups/import", response_model=SourceGroupDetailOut, status_code=201)
async def import_source_group(
    request: Request,
    group_name: str = Query(..., description="Organization/group name at the provider"),
    provider_id: int = Query(..., description="git ResourceProvider ID (external)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("source_groups:write")),
):
    """Import an organization/group from a git provider and its repositories."""
    group = await SourceGroupService.import_group(
        db,
        group_name=group_name,
        provider_id=provider_id,
        current_user=current_user,
        ip_address=request.client.host if request.client else None,
    )
    return SourceGroupDetailOut.model_validate(group)


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
    group, _provider = await SourceGroupService.refresh_group(
        db,
        group_id=group_id,
        current_user=current_user,
        ip_address=request.client.host if request.client else None,
    )
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
        .options(selectinload(SourceGroup.source_repositories))
        .where(SourceGroup.id == group_id)
    )
    group = result.unique().scalar_one_or_none()
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
# Source Repositories
# ===================================================================


@router.get("/groups/{group_id}/repositories", response_model=list[SourceRepositoryListOut])
async def list_source_repositories(
    group_id: int,
    discovery_status: str | None = Query(None, description="Filter by discovery_status"),
    is_archived: bool | None = Query(None, description="Filter archived repos"),
    search: str | None = Query(None, description="Search by name or full_name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:read")),
):
    """List repositories in a source group with optional filtering.

    Use ``group_id=0`` to list repositories across **all** non-deleted groups
    the current user has scope access to.
    """
    rbac = RBACService(db)

    if group_id == 0:
        # "All groups" — collect repositories from all accessible, non-deleted groups
        # AND orphan repositories (source_group_id IS NULL — Generic Git)
        grp_result = await db.execute(select(SourceGroup).where(~SourceGroup.is_deleted))
        all_groups = grp_result.scalars().all()
        allowed_group_ids = [
            g.id
            for g in all_groups
            if await rbac.check_scope_access(current_user.id, "source_group", g.id)
        ]

        conditions = [SourceRepository.is_deleted.is_(False)]
        group_scoped = []
        if allowed_group_ids:
            group_scoped.append(SourceRepository.source_group_id.in_(allowed_group_ids))
        # Always include orphan repos (generic git)
        group_scoped.append(SourceRepository.source_group_id.is_(None))
        conditions.append(or_(*group_scoped))

        query = (
            select(SourceRepository)
            .options(selectinload(SourceRepository.source_group))
            .where(*conditions)
        )
    else:
        # Verify group exists
        grp_result = await db.execute(
            select(SourceGroup).where(
                SourceGroup.id == group_id,
                ~SourceGroup.is_deleted,
            )
        )
        group = grp_result.scalar_one_or_none()
        if group is None:
            raise HTTPException(status_code=404, detail=f"SourceGroup with id={group_id} not found")

        if not await rbac.check_scope_access(current_user.id, "source_group", group_id):
            raise HTTPException(
                status_code=403, detail="Access denied: resource not in your role scope"
            )

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
        query = query.where(SourceRepository.full_name.ilike(f"%{search}%"))

    query = query.order_by(SourceRepository.name.asc()).offset(offset).limit(limit)

    result = await db.execute(query)
    repos = result.scalars().all()
    return [SourceRepositoryListOut.model_validate(r) for r in repos]


@router.post("/repositories", response_model=SourceRepositoryDetailOut, status_code=201)
async def create_source_repository(
    data: SourceRepositoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:write")),
):
    """Create a source repository manually (Generic Git or any provider).

    Parses clone_url to derive name/full_name, resolves the git provider
    (``provider_id`` — ResourceProvider) and launches a background
    metadata fetch.
    """
    repo = await SourceRepositoryService.create_repository(
        db,
        clone_url=data.clone_url,
        provider_type=data.provider_type,
        provider_id=data.provider_id,
        current_user=current_user,
    )

    # Launch background metadata fetch (runs in its own session)
    asyncio.create_task(fetch_metadata_background(repo.id))

    return SourceRepositoryDetailOut.model_validate(repo)


@router.get("/repositories/{repository_id}", response_model=SourceRepositoryDetailOut)
async def get_source_repository(
    repository_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:read")),
):
    """Get details of a single source repository."""
    await _get_scoped_repository(db, current_user, repository_id)
    result = await db.execute(
        select(SourceRepository)
        .options(
            selectinload(SourceRepository.source_group),
            selectinload(SourceRepository.provider),
            selectinload(SourceRepository.mirrors),
        )
        .where(SourceRepository.id == repository_id)
    )
    repo = result.unique().scalar_one()
    return SourceRepositoryDetailOut.model_validate(repo)


@router.get(
    "/repositories/{repository_id}/releases", response_model=list[SourceRepositoryReleaseOut]
)
async def get_repository_releases(
    repository_id: int,
    include_prereleases: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:read")),
):
    """List tracked releases for a source repository."""
    await _get_scoped_repository(db, current_user, repository_id)
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
    repo = await _get_scoped_repository(db, current_user, repository_id)
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
    repo = await _get_scoped_repository(db, current_user, repository_id)

    # Check for active mirrors referencing this repository
    result = await db.execute(
        select(Mirror).where(
            Mirror.source_repository_id == repo.id,
            ~Mirror.is_deleted,
        )
    )
    active_mirrors = result.scalars().all()
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
    repo = await _get_scoped_repository(db, current_user, repository_id, include_deleted=True)
    if not repo.is_deleted:
        raise HTTPException(status_code=400, detail="Source repository is not deleted")

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
    result = await db.execute(
        select(SourceRepository)
        .options(
            selectinload(SourceRepository.source_group),
            selectinload(SourceRepository.provider),
            selectinload(SourceRepository.mirrors),
        )
        .where(SourceRepository.id == repo.id)
    )
    repo = result.unique().scalar_one()
    return SourceRepositoryDetailOut.model_validate(repo)


@router.post("/repositories/{repository_id}/refresh", response_model=SourceRepositoryDetailOut)
async def refresh_source_repository(
    repository_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("source_groups:refresh")),
):
    """Re-fetch repository metadata from the upstream provider."""
    await _get_scoped_repository(db, current_user, repository_id)

    result = await db.execute(
        select(SourceRepository)
        .options(
            selectinload(SourceRepository.provider).selectinload(ResourceProvider.credential),
            selectinload(SourceRepository.mirrors),
        )
        .where(SourceRepository.id == repository_id)
    )
    repo = result.unique().scalar_one()

    await SourceRepositoryService.refresh_repository(db, repo, current_user=current_user)

    result = await db.execute(
        select(SourceRepository)
        .options(
            selectinload(SourceRepository.source_group),
            selectinload(SourceRepository.provider),
            selectinload(SourceRepository.mirrors),
        )
        .where(SourceRepository.id == repo.id)
    )
    repo = result.unique().scalar_one()
    return SourceRepositoryDetailOut.model_validate(repo)


# ===================================================================
# Mirrors
# ===================================================================


@router.get("/mirrors", response_model=list[MirrorListOut])
async def list_mirrors(
    source_group_id: int | None = Query(None),
    sync_group_id: int | None = Query(None),
    status_flag: int | None = Query(None, ge=0, le=4),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
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

    items, _total = await MirrorService.get_mirrors(
        db,
        filters=filters,
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
    mirror = await MirrorService.get_mirror_detail(db, mirror_id)
    rbac = RBACService(db)
    if not await rbac.check_scope_access(current_user.id, "sync_group", mirror.sync_group_id):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )
    return MirrorDetailOut.model_validate(mirror)


@router.post("/mirrors", response_model=MirrorDetailOut, status_code=201)
async def create_mirror(
    data: MirrorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("mirrors:write")),
):
    """Create a single mirror for a source repository."""
    mirror = await MirrorService.create_mirror(
        db,
        data=data,
        user_id=current_user.id,
        username=current_user.username,
    )
    return MirrorDetailOut.model_validate(mirror)


@router.post("/mirrors/bulk", response_model=list[MirrorListOut], status_code=201)
async def bulk_create_mirrors(
    data: MirrorBulkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("mirrors:write")),
):
    """Create multiple mirrors in a single batch operation."""
    mirrors = await MirrorService.bulk_create_mirrors(
        db,
        data=data,
        user_id=current_user.id,
        username=current_user.username,
    )
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
    await _check_sync_group_scope(db, current_user, mirror_id)
    mirror = await MirrorService.update_mirror(
        db,
        mirror_id=mirror_id,
        data=data,
        username=current_user.username,
    )
    return MirrorDetailOut.model_validate(mirror)


@router.delete("/mirrors/{mirror_id}", status_code=204)
async def delete_mirror(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:delete")),
):
    """Soft-delete a mirror."""
    await _check_sync_group_scope(db, current_user, mirror_id)
    await MirrorService.soft_delete_mirror(
        db,
        mirror_id=mirror_id,
        username=current_user.username,
    )


@router.post("/mirrors/{mirror_id}/restore", response_model=MirrorDetailOut)
async def restore_mirror(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:delete")),
):
    """Restore a soft-deleted mirror (scope check includes soft-deleted)."""
    await _check_sync_group_scope(db, current_user, mirror_id, include_deleted=True)
    mirror = await MirrorService.restore_mirror(
        db,
        mirror_id=mirror_id,
        username=current_user.username,
    )
    return MirrorDetailOut.model_validate(mirror)


@router.post("/mirrors/{mirror_id}/sync", response_model=MirrorLogOut, status_code=201)
async def trigger_mirror_sync(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:sync")),
):
    """Trigger a sync pipeline for a mirror."""
    await _check_sync_group_scope(db, current_user, mirror_id)
    mirror_log = await MirrorService.trigger_sync(
        db,
        mirror_id=mirror_id,
        user_id=current_user.id,
        username=current_user.username,
    )
    return MirrorLogOut.model_validate(mirror_log)


@router.post("/mirrors/{mirror_id}/freshness", response_model=MirrorLogOut, status_code=201)
async def check_mirror_freshness(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_permission("mirrors:sync")),
):
    """Run a freshness check comparing source HEAD against last known commit."""
    await _check_sync_group_scope(db, current_user, mirror_id)
    mirror_log = await MirrorService.check_freshness(
        db,
        mirror_id=mirror_id,
        username=current_user.username,
    )
    return MirrorLogOut.model_validate(mirror_log)


@router.post("/mirrors/import", response_model=MirrorDetailOut, status_code=201)
async def import_mirror(
    data: ImportMirrorRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("mirrors:import")),
):
    """Import (register) an existing mirror for a source repository."""
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
    return await MirrorService.check_duplicates(
        db,
        source_repo_ids=data.source_repo_ids,
        sync_group_id=data.sync_group_id,
    )


@router.get("/mirrors/{mirror_id}/logs", response_model=list[MirrorLogOut])
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
    await _check_sync_group_scope(db, current_user, mirror_id)
    logs = await MirrorService.get_logs(
        db,
        mirror_id=mirror_id,
        log_type=log_type,
        limit=limit,
        offset=offset,
    )
    return [MirrorLogOut.model_validate(log) for log in logs]


# ===================================================================
# Sync Groups
# ===================================================================


@router.get("/sync-groups", response_model=list[SyncGroupOut])
async def list_sync_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sync_groups:read")),
):
    """List all sync groups with RBAC-scoped filtering."""
    groups = await SyncGroupService.get_sync_groups(db, user=current_user)
    return [SyncGroupOut.model_validate(g) for g in groups]


@router.post("/sync-groups", response_model=SyncGroupOut, status_code=201)
async def create_sync_group(
    data: SyncGroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sync_groups:write")),
):
    """Create a new sync group."""
    group = await SyncGroupService.create_sync_group(
        db,
        data=data,
        user_id=current_user.id,
        username=current_user.username,
    )
    return SyncGroupOut.model_validate(group)


@router.get("/sync-groups/{group_id}", response_model=SyncGroupOut)
async def get_sync_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_scope_permission("sync_groups:read", "sync_group", "group_id")),
):
    """Get details of a single sync group."""
    group = await SyncGroupService.get_sync_group(db, group_id)
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
    group = await SyncGroupService.update_sync_group(
        db,
        group_id=group_id,
        data=data,
        username=current_user.username,
    )
    return SyncGroupOut.model_validate(group)


@router.delete("/sync-groups/{group_id}", status_code=204)
async def delete_sync_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(require_scope_permission("sync_groups:delete", "sync_group", "group_id")),
):
    """Soft-delete a sync group (mirrors are migrated to default group)."""
    await SyncGroupService.delete_sync_group(db, group_id)


@router.post("/sync-groups/{group_id}/restore", response_model=SyncGroupOut)
async def restore_sync_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("sync_groups:delete", "sync_group", "group_id")),
):
    """Restore a soft-deleted sync group."""
    group = await SyncGroupService.restore_sync_group(
        db,
        group_id=group_id,
        user_id=current_user.id,
        username=current_user.username,
    )
    return SyncGroupOut.model_validate(group)


@router.post("/sync-groups/{group_id}/mirrors/bulk", response_model=SyncGroupOut)
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
    group = await SyncGroupService.bulk_assign_mirrors(
        db,
        sync_group_id=group_id,
        mirror_ids=data.mirror_ids,
        user_id=current_user.id,
        username=current_user.username,
    )
    return SyncGroupOut.model_validate(group)


# ────────────────────────────────────────────────────────────────────────────
# Integrity Check (direct, no CI/CD pipeline)
# ────────────────────────────────────────────────────────────────────────────


@router.post("/mirrors/{mirror_id}/integrity-check", response_model=IntegrityCheckResult)
async def check_mirror_integrity(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compare source HEAD commit against target GitLab project directly.

    Does NOT trigger a CI/CD pipeline — fetches commits from both sides
    and returns a comparison result (MATCH / MISMATCH / ERROR).
    """
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


@router.post("/sync-groups/{group_id}/apply-pipeline", response_model=SyncGroupOut)
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
    group = await SyncGroupService.apply_pipeline(
        db,
        sync_group_id=group_id,
        pipeline_id=request.pipeline_id,
        user_id=current_user.id,
        username=current_user.username,
    )
    return SyncGroupOut.model_validate(group)
