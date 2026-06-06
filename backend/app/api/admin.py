from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CannotModifyBuiltinRoleError,
    PermissionNotFoundError,
    RoleHasUsersError,
    RoleNotFoundError,
)
from app.core.rbac import require_admin, require_permission
from app.core.security import get_password_hash
from app.database import get_db
from app.models.role import Role, UserRole
from app.models.user import User
from app.schemas.auth import UserCreate, UserOut, UserUpdate
from app.schemas.rbac import PermissionOut, RoleCreate, RoleDetailOut, RoleUpdate
from app.services.rbac_service import RBACService

router = APIRouter()


@router.get("/users", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin()),
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
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin()),
):
    # Check uniqueness
    existing = await db.execute(
        select(User).where(
            (User.username == data.username) | (User.email == data.email)
        )
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
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin()),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

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
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin()),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    await db.delete(user)
    await db.commit()


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Role not found"
        )
    return role


@router.post(
    "/roles", response_model=RoleDetailOut, status_code=status.HTTP_201_CREATED
)
async def create_role(
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("roles:write")),
):
    """Create a new custom role with permissions."""
    service = RBACService(db)
    try:
        return await service.create_role(
            name=data.name,
            description=data.description,
            permission_names=data.permission_names,
            created_by_user_id=current_user.id,
        )
    except PermissionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/roles/{role_id}", response_model=RoleDetailOut)
async def update_role(
    role_id: int,
    data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:write")),
):
    """Update an existing custom role. Built-in roles cannot be modified."""
    service = RBACService(db)
    try:
        return await service.update_role(
            role_id=role_id,
            name=data.name,
            description=data.description,
            permission_names=data.permission_names,
        )
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CannotModifyBuiltinRoleError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("roles:delete")),
):
    """Delete a custom role. Built-in roles and roles with users cannot be deleted."""
    service = RBACService(db)
    try:
        await service.delete_role(role_id)
    except RoleNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except CannotModifyBuiltinRoleError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RoleHasUsersError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
