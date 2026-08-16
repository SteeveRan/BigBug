import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CannotModifyBuiltinRoleError,
    PermissionNotFoundError,
    RoleHasUsersError,
    RoleNotFoundError,
)
from app.core.rbac import require_permission
from app.core.security import get_password_hash
from app.database import get_db
from app.models.role import Role, UserRole
from app.models.user import User
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.schemas.rbac import (
    PermissionOut,
    RoleCreate,
    RoleDetailOut,
    RoleScopeOut,
    RoleScopeUpdate,
    RoleUpdate,
)
from app.services.audit import AuditService
from app.services.rbac_service import RBACService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("users:read")),
):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return [
        UserOut(
            id=u.id,
            username=u.username,
            email=u.email,
            is_active=u.is_active,
            roles=[r.name for r in u.roles],
        )
        for u in users
    ]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("users:write")),
):
    # Check uniqueness
    existing = await db.execute(
        select(User).where((User.username == data.username) | (User.email == data.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
    )
    db.add(user)
    await db.flush()

    # Assign roles
    for role_name in data.roles:
        role_result = await db.execute(select(Role).where(Role.name == role_name))
        role = role_result.scalar_one_or_none()
        if role:
            db.add(UserRole(user_id=user.id, role_id=role.id))

    await db.commit()
    await db.refresh(user)

    # Audit log: user created
    await AuditService.log_event(
        db,
        user_id=user.id,
        username=user.username,
        action="create",
        resource_type="user",
        resource_id=user.id,
        resource_name=user.username,
        ip_address=request.client.host if request.client else None,
    )

    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        roles=[r.name for r in user.roles],
    )


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    data: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("users:write")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if data.email is not None:
        user.email = data.email
    if data.is_active is not None:
        user.is_active = data.is_active

    if data.roles is not None:
        # Remove existing roles
        await db.execute(UserRole.__table__.delete().where(UserRole.user_id == user_id))
        for role_name in data.roles:
            role_result = await db.execute(select(Role).where(Role.name == role_name))
            role = role_result.scalar_one_or_none()
            if role:
                db.add(UserRole(user_id=user.id, role_id=role.id))

    await db.commit()
    await db.refresh(user)

    # Audit log: user updated
    await AuditService.log_event(
        db,
        user_id=user.id,
        username=user.username,
        action="update",
        resource_type="user",
        resource_id=user.id,
        resource_name=user.username,
        ip_address=request.client.host if request.client else None,
    )

    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        roles=[r.name for r in user.roles],
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("users:delete")),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    username = user.username
    await db.delete(user)
    await db.commit()

    # Audit log: user deleted. The user row no longer exists, so ``user_id``
    # must be NULL — otherwise the audit insert violates ``audit_logs_user_id_fkey``
    # and poisons the session (PendingRollbackError) for subsequent requests.
    await AuditService.log_event(
        db,
        user_id=None,
        username=username,
        action="delete",
        resource_type="user",
        resource_id=user_id,
        resource_name=username,
        ip_address=request.client.host if request.client else None,
    )


# ------------------------------------------------------------------
# RBAC — Permissions
# ------------------------------------------------------------------


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    """Return all available permissions in the system."""
    service = RBACService(db)
    return await service.get_all_permissions()


# ------------------------------------------------------------------
# RBAC — Roles CRUD
# ------------------------------------------------------------------


@router.get(
    "/roles/{role_id}/users",
    response_model=list[UserOut],
    tags=["admin"],
)
async def list_role_users(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    """List all users assigned to a specific role."""
    service = RBACService(db)
    role = await service.get_role_by_id(role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    users = await service.get_role_users(role_id)
    return [
        UserOut(
            id=u.id,
            username=u.username,
            email=u.email,
            is_active=u.is_active,
            roles=[r.name for r in u.roles],
        )
        for u in users
    ]


@router.get("/roles", response_model=list[RoleDetailOut])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    """List all roles with their assigned permissions."""
    service = RBACService(db)
    return await service.get_all_roles()


@router.get("/roles/{role_id}", response_model=RoleDetailOut)
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    """Get a single role by ID."""
    service = RBACService(db)
    role = await service.get_role_by_id(role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.post("/roles", response_model=RoleDetailOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("roles:write")),
):
    """Create a new custom role with permissions."""
    service = RBACService(db)
    try:
        role = await service.create_role(
            name=data.name,
            description=data.description,
            permission_names=data.permission_names,
            created_by_user_id=current_user.id,
        )
    except PermissionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    # Audit log: role created
    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="create",
        resource_type="role",
        resource_id=role.id,
        resource_name=role.name,
        ip_address=request.client.host if request.client else None,
    )

    return role


@router.patch("/roles/{role_id}", response_model=RoleDetailOut)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("roles:write")),
):
    """Update an existing custom role. Built-in roles cannot be modified."""
    service = RBACService(db)
    try:
        role = await service.update_role(
            role_id=role_id,
            name=data.name,
            description=data.description,
            permission_names=data.permission_names,
        )
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except PermissionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except CannotModifyBuiltinRoleError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e

    # Audit log: role updated
    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="update",
        resource_type="role",
        resource_id=role.id,
        resource_name=role.name,
        ip_address=request.client.host if request.client else None,
    )

    return role


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("roles:delete")),
):
    """Delete a custom role. Built-in roles and roles with users cannot be deleted."""
    service = RBACService(db)
    # Get role name before deletion for audit
    role = await service.get_role_by_id(role_id)
    role_name = role.name if role else f"role_{role_id}"
    try:
        await service.delete_role(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except CannotModifyBuiltinRoleError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except RoleHasUsersError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e

    # Audit log: role deleted
    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="delete",
        resource_type="role",
        resource_id=role_id,
        resource_name=role_name,
        ip_address=request.client.host if request.client else None,
    )


# ------------------------------------------------------------------
# RBAC — Role Scope: Source Groups
# ------------------------------------------------------------------


@router.get(
    "/roles/{role_id}/scopes/source-groups",
    response_model=RoleScopeOut,
    tags=["admin"],
)
async def get_role_scope_source_groups(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    """Get source groups scope for a role."""
    service = RBACService(db)
    try:
        source_group_ids = await service.get_role_scope_source_groups(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(source_group_ids=source_group_ids)


@router.post(
    "/roles/{role_id}/scopes/source-groups",
    response_model=RoleScopeOut,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def add_role_scope_source_group(
    role_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Add a single source group to role scope."""
    source_group_id = body.get("source_group_id")
    if source_group_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'source_group_id' is required",
        )

    service = RBACService(db)
    try:
        await service.add_role_scope_source_group(role_id, int(source_group_id))
        source_group_ids = await service.get_role_scope_source_groups(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(source_group_ids=source_group_ids)


@router.put(
    "/roles/{role_id}/scopes/source-groups",
    response_model=RoleScopeOut,
    tags=["admin"],
)
async def set_role_scope_source_groups(
    role_id: int,
    data: RoleScopeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Replace all source groups scope for a role (atomic)."""
    service = RBACService(db)
    try:
        await service.set_role_scope_source_groups(role_id, data.source_group_ids or [])
        source_group_ids = await service.get_role_scope_source_groups(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(source_group_ids=source_group_ids)


@router.delete(
    "/roles/{role_id}/scopes/source-groups/{source_group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def remove_role_scope_source_group(
    role_id: int,
    source_group_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Remove a single source group from role scope."""
    service = RBACService(db)
    try:
        await service.remove_role_scope_source_group(role_id, source_group_id)
    except Exception as e:
        logger.exception(
            "Failed to remove source group scope: role_id=%s, source_group_id=%s",
            role_id,
            source_group_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error"
        ) from e


# ------------------------------------------------------------------
# RBAC — Role Scope: Credentials
# ------------------------------------------------------------------


@router.get(
    "/roles/{role_id}/scopes/credentials",
    response_model=RoleScopeOut,
    tags=["admin"],
)
async def get_role_scope_credentials(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    """Get credentials scope for a role."""
    service = RBACService(db)
    try:
        credential_ids = await service.get_role_scope_credentials(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(credential_ids=credential_ids)


@router.post(
    "/roles/{role_id}/scopes/credentials",
    response_model=RoleScopeOut,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def add_role_scope_credential(
    role_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Add a single credential to role scope."""
    credential_id = body.get("credential_id")
    if credential_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'credential_id' is required",
        )

    service = RBACService(db)
    try:
        await service.add_role_scope_credential(role_id, int(credential_id))
        credential_ids = await service.get_role_scope_credentials(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(credential_ids=credential_ids)


@router.put(
    "/roles/{role_id}/scopes/credentials",
    response_model=RoleScopeOut,
    tags=["admin"],
)
async def set_role_scope_credentials(
    role_id: int,
    data: RoleScopeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Replace all credentials scope for a role (atomic)."""
    service = RBACService(db)
    try:
        await service.set_role_scope_credentials(role_id, data.credential_ids or [])
        credential_ids = await service.get_role_scope_credentials(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(credential_ids=credential_ids)


@router.delete(
    "/roles/{role_id}/scopes/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def remove_role_scope_credential(
    role_id: int,
    credential_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Remove a single credential from role scope."""
    service = RBACService(db)
    try:
        await service.remove_role_scope_credential(role_id, credential_id)
    except Exception as e:
        logger.exception(
            "Failed to remove credential scope: role_id=%s, credential_id=%s",
            role_id,
            credential_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error"
        ) from e


# ------------------------------------------------------------------
# Manual cleanup — trigger physical deletion of soft-deleted records
# ------------------------------------------------------------------


@router.post("/cleanup", tags=["admin"], status_code=status.HTTP_200_OK)
async def manual_cleanup(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("system:config")),
) -> dict:
    """Manually trigger physical deletion of soft-deleted Mirroring entities.

    All records with ``deleted_at`` older than the configured retention
    period (``SOFT_DELETE_RETENTION_DAYS``) are permanently removed.

    Cascade order: MirrorLog → Mirror → SyncGroup → SourceRepository →
    SourceGroup → Pipeline.
    """
    from app.services.cleanup import CleanupService

    result = await CleanupService.run_cleanup(db)
    logger.info("Manual cleanup executed by admin: %s", result.to_dict())
    return result.to_dict()


# ------------------------------------------------------------------
# RBAC — Role Scope: Sync Groups
# ------------------------------------------------------------------


@router.get(
    "/roles/{role_id}/scopes/sync-groups",
    response_model=RoleScopeOut,
    tags=["admin"],
)
async def get_role_scope_sync_groups(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    """Get sync groups scope for a role."""
    service = RBACService(db)
    try:
        sync_group_ids = await service.get_role_scope_sync_groups(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(sync_group_ids=sync_group_ids)


@router.post(
    "/roles/{role_id}/scopes/sync-groups",
    response_model=RoleScopeOut,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def add_role_scope_sync_group(
    role_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Add a single sync group to role scope."""
    sync_group_id = body.get("sync_group_id")
    if sync_group_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'sync_group_id' is required",
        )

    service = RBACService(db)
    try:
        await service.add_role_scope_sync_group(role_id, int(sync_group_id))
        sync_group_ids = await service.get_role_scope_sync_groups(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(sync_group_ids=sync_group_ids)


@router.put(
    "/roles/{role_id}/scopes/sync-groups",
    response_model=RoleScopeOut,
    tags=["admin"],
)
async def set_role_scope_sync_groups(
    role_id: int,
    data: RoleScopeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Replace all sync groups scope for a role (atomic)."""
    service = RBACService(db)
    try:
        await service.set_role_scope_sync_groups(role_id, data.sync_group_ids or [])
        sync_group_ids = await service.get_role_scope_sync_groups(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(sync_group_ids=sync_group_ids)


@router.delete(
    "/roles/{role_id}/scopes/sync-groups/{sync_group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def remove_role_scope_sync_group(
    role_id: int,
    sync_group_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Remove a single sync group from role scope."""
    service = RBACService(db)
    try:
        await service.remove_role_scope_sync_group(role_id, sync_group_id)
    except Exception as e:
        logger.exception(
            "Failed to remove sync group scope: role_id=%s, sync_group_id=%s",
            role_id,
            sync_group_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error"
        ) from e


# ------------------------------------------------------------------
# RBAC — Role Scope: Providers
# ------------------------------------------------------------------


@router.get(
    "/roles/{role_id}/scopes/providers",
    response_model=RoleScopeOut,
    tags=["admin"],
)
async def get_role_scope_providers(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:read")),
):
    """Get providers scope for a role."""
    service = RBACService(db)
    try:
        provider_ids = await service.get_role_scope_providers(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(provider_ids=provider_ids)


@router.post(
    "/roles/{role_id}/scopes/providers",
    response_model=RoleScopeOut,
    status_code=status.HTTP_201_CREATED,
    tags=["admin"],
)
async def add_role_scope_provider(
    role_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Add a single provider to role scope."""
    provider_id = body.get("provider_id")
    if provider_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Field 'provider_id' is required",
        )

    service = RBACService(db)
    try:
        await service.add_role_scope_provider(role_id, int(provider_id))
        provider_ids = await service.get_role_scope_providers(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(provider_ids=provider_ids)


@router.put(
    "/roles/{role_id}/scopes/providers",
    response_model=RoleScopeOut,
    tags=["admin"],
)
async def set_role_scope_providers(
    role_id: int,
    data: RoleScopeUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Replace all providers scope for a role (atomic)."""
    service = RBACService(db)
    try:
        await service.set_role_scope_providers(role_id, data.provider_ids or [])
        provider_ids = await service.get_role_scope_providers(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e

    return RoleScopeOut(provider_ids=provider_ids)


@router.delete(
    "/roles/{role_id}/scopes/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def remove_role_scope_provider(
    role_id: int,
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Remove a single provider from role scope."""
    service = RBACService(db)
    try:
        await service.remove_role_scope_provider(role_id, provider_id)
    except Exception as e:
        logger.exception(
            "Failed to remove provider scope: role_id=%s, provider_id=%s",
            role_id,
            provider_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error"
        ) from e
