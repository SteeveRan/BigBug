"""
RBAC Service — business logic for permission-based access control.

Handles:
- Loading user permissions from DB (via role → role_permissions → permissions)
- Role CRUD operations
- Permission assignments
- Seeding default permissions

All methods are pure domain logic and raise domain exceptions (not HTTPException).
The API layer is responsible for mapping those exceptions to HTTP responses.
"""

from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.role import Role, UserRole
from app.models.permission import Permission, role_permissions
from app.core.exceptions import (
    PermissionNotFoundError,
    CannotModifyBuiltinRoleError,
    RoleHasUsersError,
    RoleNotFoundError,
)


class RBACService:
    """Core business logic for RBAC (permissions, roles)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Permission queries
    # ------------------------------------------------------------------

    async def get_user_permissions(self, user_id: int) -> list[str]:
        """
        Get list of permission names for a user via their role.

        Query: User → user_roles → Role → role_permissions → Permission
        Returns a flat list of ``"resource:action"`` strings.
        """
        stmt = (
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.permissions)
            )
            .where(User.id == user_id)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None or not user.user_roles:
            return []

        # Collect permissions across all roles
        permission_names: list[str] = []
        seen: set[str] = set()
        for user_role in user.user_roles:
            if user_role.role is not None:
                for p in user_role.role.permissions:
                    if p.name not in seen:
                        seen.add(p.name)
                        permission_names.append(p.name)

        return permission_names

    async def get_all_permissions(self) -> list[Permission]:
        """Get all available permissions in the system."""
        result = await self.db.execute(
            select(Permission).order_by(Permission.name)
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Role queries
    # ------------------------------------------------------------------

    async def get_all_roles(self) -> list[Role]:
        """Get all roles with their permissions pre-loaded."""
        result = await self.db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .order_by(Role.name)
        )
        return list(result.scalars().all())

    async def get_role_by_id(self, role_id: int) -> Role | None:
        """Get a single role with permissions, or None."""
        result = await self.db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.id == role_id)
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Role CRUD
    # ------------------------------------------------------------------

    async def _resolve_permissions(self, permission_names: list[str]) -> list[Permission]:
        """
        Fetch Permission objects for a list of permission name strings.
        Raises PermissionNotFoundError if any name is unknown.
        """
        result = await self.db.execute(
            select(Permission).where(Permission.name.in_(permission_names))
        )
        found = list(result.scalars().all())
        found_names = {p.name for p in found}

        missing = set(permission_names) - found_names
        if missing:
            raise PermissionNotFoundError(
                f"Unknown permission(s): {', '.join(sorted(missing))}"
            )
        return found

    async def create_role(
        self,
        name: str,
        description: str | None,
        permission_names: list[str],
        created_by_user_id: int,
    ) -> Role:
        """Create a custom role with specified permissions."""
        permissions = await self._resolve_permissions(permission_names)

        role = Role(
            name=name,
            description=description,
            is_custom=True,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(role)
        await self.db.flush()

        role.permissions = permissions
        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def update_role(
        self,
        role_id: int,
        name: str | None,
        description: str | None,
        permission_names: list[str] | None,
    ) -> Role:
        """Update role name, description, and/or permissions."""
        role = await self.get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role with id={role_id} not found")

        if not role.is_custom:
            raise CannotModifyBuiltinRoleError(
                f"Role '{role.name}' is a built-in role and cannot be modified."
            )

        if name is not None:
            role.name = name
        if description is not None:
            role.description = description

        if permission_names is not None:
            permissions = await self._resolve_permissions(permission_names)
            role.permissions = permissions

        await self.db.commit()
        await self.db.refresh(role)
        return role

    async def delete_role(self, role_id: int) -> None:
        """Delete a custom role. Raises if role is built-in or has users."""
        role = await self.get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role with id={role_id} not found")

        if not role.is_custom:
            raise CannotModifyBuiltinRoleError(
                f"Role '{role.name}' is a built-in role and cannot be deleted."
            )

        # Check if any users have this role
        user_count_result = await self.db.execute(
            select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
        )
        user_count = user_count_result.scalar() or 0
        if user_count > 0:
            raise RoleHasUsersError(
                f"Cannot delete role '{role.name}': {user_count} user(s) are still assigned."
            )

        await self.db.delete(role)
        await self.db.commit()

    async def assign_permissions_to_role(
        self, role_id: int, permission_names: list[str]
    ) -> Role:
        """Replace all permissions for a role with the given set."""
        role = await self.get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role with id={role_id} not found")

        permissions = await self._resolve_permissions(permission_names)
        role.permissions = permissions

        await self.db.commit()
        await self.db.refresh(role)
        return role
