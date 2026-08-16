"""
RBAC Service — business logic for permission-based access control.

Handles:
- Loading user permissions from DB (via role → role_permissions → permissions)
- Role CRUD operations
- Permission assignments
- Seeding default permissions
- Role-scope management (source groups, credentials, sync groups, providers)
- Effective scope computation and scope-based access checks

All methods are pure domain logic and raise domain exceptions (not HTTPException).
The API layer is responsible for mapping those exceptions to HTTP responses.
"""

import logging

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    CannotModifyBuiltinRoleError,
    PermissionNotFoundError,
    RoleHasUsersError,
    RoleNotFoundError,
)
from app.models.permission import Permission
from app.models.role import Role, UserRole
from app.models.role_scope import (
    RoleScopeCredential,
    RoleScopeProvider,
    RoleScopeSourceGroup,
    RoleScopeSyncGroup,
)
from app.models.team import TeamRole
from app.models.team_member import TeamMember
from app.models.user import User

logger = logging.getLogger(__name__)


class RBACService:
    """Core business logic for RBAC (permissions, roles, scope)."""

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
        result = await self.db.execute(select(Permission).order_by(Permission.name))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Role queries
    # ------------------------------------------------------------------

    async def _get_roles_with_users_count(self, role_query: select) -> list[Role]:
        """Execute a role query and annotate each result with users_count."""
        result = await self.db.execute(role_query)
        roles = list(result.scalars().all())

        # Batch-fetch users_count for all roles in one query
        role_ids = [r.id for r in roles]
        if role_ids:
            count_stmt = (
                select(UserRole.role_id, func.count().label("cnt"))
                .where(UserRole.role_id.in_(role_ids))
                .group_by(UserRole.role_id)
            )
            count_result = await self.db.execute(count_stmt)
            counts: dict[int, int] = {row.role_id: row.cnt for row in count_result}
        else:
            counts = {}

        for role in roles:
            role.users_count = counts.get(role.id, 0)

        return roles

    async def get_all_roles(self) -> list[Role]:
        """Get all roles with their permissions pre-loaded and users_count."""
        query = select(Role).options(selectinload(Role.permissions)).order_by(Role.name)
        return await self._get_roles_with_users_count(query)

    async def get_role_by_id(self, role_id: int) -> Role | None:
        """Get a single role with permissions and users_count, or None."""
        query = select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
        roles = await self._get_roles_with_users_count(query)
        return roles[0] if roles else None

    async def get_role_users(self, role_id: int) -> list[User]:
        """Get all users assigned to a specific role."""
        result = await self.db.execute(
            select(User)
            .join(UserRole, UserRole.user_id == User.id)
            .where(UserRole.role_id == role_id)
            .order_by(User.username)
        )
        return list(result.scalars().all())

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
            raise PermissionNotFoundError(f"Unknown permission(s): {', '.join(sorted(missing))}")
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

    async def assign_permissions_to_role(self, role_id: int, permission_names: list[str]) -> Role:
        """Replace all permissions for a role with the given set."""
        role = await self.get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role with id={role_id} not found")

        permissions = await self._resolve_permissions(permission_names)
        role.permissions = permissions

        await self.db.commit()
        await self.db.refresh(role)
        return role

    # ------------------------------------------------------------------
    # Source Groups scope
    # ------------------------------------------------------------------

    async def get_role_scope_source_groups(self, role_id: int) -> list[int]:
        """Return list of source_group_ids assigned to this role."""
        result = await self.db.execute(
            select(RoleScopeSourceGroup.source_group_id).where(
                RoleScopeSourceGroup.role_id == role_id
            )
        )
        return sorted(row.source_group_id for row in result)

    async def set_role_scope_source_groups(self, role_id: int, source_group_ids: list[int]) -> None:
        """Atomic replace: delete all existing scope for this role + insert new ones."""
        # Verify role exists
        role = await self.get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role with id={role_id} not found")

        # Delete all existing scope entries for this role
        await self.db.execute(
            delete(RoleScopeSourceGroup).where(RoleScopeSourceGroup.role_id == role_id)
        )

        # Insert new scope entries
        for sg_id in source_group_ids:
            self.db.add(RoleScopeSourceGroup(role_id=role_id, source_group_id=sg_id))

        await self.db.commit()
        logger.debug(
            "set_role_scope_source_groups: role_id=%s, count=%s",
            role_id,
            len(source_group_ids),
        )

    async def add_role_scope_source_group(
        self, role_id: int, source_group_id: int, is_auto_added: bool = False
    ) -> None:
        """
        Add single source_group to role scope (idempotent — no error if already exists).
        ``is_auto_added`` is reserved for future use (auto-scoping on sync group creation).
        """
        existing = await self.db.get(RoleScopeSourceGroup, (role_id, source_group_id))
        if existing is not None:
            return  # already exists, idempotent

        self.db.add(RoleScopeSourceGroup(role_id=role_id, source_group_id=source_group_id))
        await self.db.commit()
        logger.debug(
            "add_role_scope_source_group: role_id=%s, source_group_id=%s, is_auto_added=%s",
            role_id,
            source_group_id,
            is_auto_added,
        )

    async def remove_role_scope_source_group(self, role_id: int, source_group_id: int) -> None:
        """Remove single source_group from role scope (idempotent — no error if not found)."""
        await self.db.execute(
            delete(RoleScopeSourceGroup).where(
                RoleScopeSourceGroup.role_id == role_id,
                RoleScopeSourceGroup.source_group_id == source_group_id,
            )
        )
        await self.db.commit()
        logger.debug(
            "remove_role_scope_source_group: role_id=%s, source_group_id=%s",
            role_id,
            source_group_id,
        )

    # ------------------------------------------------------------------
    # Credentials scope
    # ------------------------------------------------------------------

    async def get_role_scope_credentials(self, role_id: int) -> list[int]:
        """Return list of credential_ids assigned to this role."""
        result = await self.db.execute(
            select(RoleScopeCredential.credential_id).where(RoleScopeCredential.role_id == role_id)
        )
        return sorted(row.credential_id for row in result)

    async def set_role_scope_credentials(self, role_id: int, credential_ids: list[int]) -> None:
        """Atomic replace: delete all existing scope for this role + insert new ones."""
        role = await self.get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role with id={role_id} not found")

        await self.db.execute(
            delete(RoleScopeCredential).where(RoleScopeCredential.role_id == role_id)
        )

        for cred_id in credential_ids:
            self.db.add(RoleScopeCredential(role_id=role_id, credential_id=cred_id))

        await self.db.commit()
        logger.debug(
            "set_role_scope_credentials: role_id=%s, count=%s",
            role_id,
            len(credential_ids),
        )

    async def add_role_scope_credential(self, role_id: int, credential_id: int) -> None:
        """Add single credential to role scope (idempotent)."""
        existing = await self.db.get(RoleScopeCredential, (role_id, credential_id))
        if existing is not None:
            return

        self.db.add(RoleScopeCredential(role_id=role_id, credential_id=credential_id))
        await self.db.commit()
        logger.debug(
            "add_role_scope_credential: role_id=%s, credential_id=%s",
            role_id,
            credential_id,
        )

    async def remove_role_scope_credential(self, role_id: int, credential_id: int) -> None:
        """Remove single credential from role scope (idempotent)."""
        await self.db.execute(
            delete(RoleScopeCredential).where(
                RoleScopeCredential.role_id == role_id,
                RoleScopeCredential.credential_id == credential_id,
            )
        )
        await self.db.commit()
        logger.debug(
            "remove_role_scope_credential: role_id=%s, credential_id=%s",
            role_id,
            credential_id,
        )

    # ------------------------------------------------------------------
    # Sync Groups scope
    # ------------------------------------------------------------------

    async def get_role_scope_sync_groups(self, role_id: int) -> list[int]:
        """Return list of sync_group_ids assigned to this role."""
        result = await self.db.execute(
            select(RoleScopeSyncGroup.sync_group_id).where(RoleScopeSyncGroup.role_id == role_id)
        )
        return sorted(row.sync_group_id for row in result)

    async def set_role_scope_sync_groups(self, role_id: int, sync_group_ids: list[int]) -> None:
        """Atomic replace: delete all existing scope for this role + insert new ones."""
        role = await self.get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role with id={role_id} not found")

        await self.db.execute(
            delete(RoleScopeSyncGroup).where(RoleScopeSyncGroup.role_id == role_id)
        )

        for sg_id in sync_group_ids:
            self.db.add(RoleScopeSyncGroup(role_id=role_id, sync_group_id=sg_id))

        await self.db.commit()
        logger.debug(
            "set_role_scope_sync_groups: role_id=%s, count=%s",
            role_id,
            len(sync_group_ids),
        )

    async def add_role_scope_sync_group(
        self, role_id: int, sync_group_id: int, is_auto_added: bool = False
    ) -> None:
        """
        Add single sync_group to role scope (idempotent).
        ``is_auto_added`` is reserved for future use (auto-scoping on sync group creation).
        """
        existing = await self.db.get(RoleScopeSyncGroup, (role_id, sync_group_id))
        if existing is not None:
            return

        self.db.add(RoleScopeSyncGroup(role_id=role_id, sync_group_id=sync_group_id))
        await self.db.commit()
        logger.debug(
            "add_role_scope_sync_group: role_id=%s, sync_group_id=%s, is_auto_added=%s",
            role_id,
            sync_group_id,
            is_auto_added,
        )

    async def remove_role_scope_sync_group(self, role_id: int, sync_group_id: int) -> None:
        """Remove single sync_group from role scope (idempotent)."""
        await self.db.execute(
            delete(RoleScopeSyncGroup).where(
                RoleScopeSyncGroup.role_id == role_id,
                RoleScopeSyncGroup.sync_group_id == sync_group_id,
            )
        )
        await self.db.commit()
        logger.debug(
            "remove_role_scope_sync_group: role_id=%s, sync_group_id=%s",
            role_id,
            sync_group_id,
        )

    # ------------------------------------------------------------------
    # Providers scope
    # ------------------------------------------------------------------

    async def get_role_scope_providers(self, role_id: int) -> list[int]:
        """Return list of provider_ids assigned to this role."""
        result = await self.db.execute(
            select(RoleScopeProvider.provider_id).where(RoleScopeProvider.role_id == role_id)
        )
        return sorted(row.provider_id for row in result)

    async def set_role_scope_providers(self, role_id: int, provider_ids: list[int]) -> None:
        """Atomic replace: delete all existing scope for this role + insert new ones."""
        role = await self.get_role_by_id(role_id)
        if role is None:
            raise RoleNotFoundError(f"Role with id={role_id} not found")

        await self.db.execute(delete(RoleScopeProvider).where(RoleScopeProvider.role_id == role_id))

        for provider_id in provider_ids:
            self.db.add(RoleScopeProvider(role_id=role_id, provider_id=provider_id))

        await self.db.commit()
        logger.debug(
            "set_role_scope_providers: role_id=%s, count=%s",
            role_id,
            len(provider_ids),
        )

    async def add_role_scope_provider(self, role_id: int, provider_id: int) -> None:
        """Add single provider to role scope (idempotent)."""
        existing = await self.db.get(RoleScopeProvider, (role_id, provider_id))
        if existing is not None:
            return

        self.db.add(RoleScopeProvider(role_id=role_id, provider_id=provider_id))
        await self.db.commit()
        logger.debug(
            "add_role_scope_provider: role_id=%s, provider_id=%s",
            role_id,
            provider_id,
        )

    async def remove_role_scope_provider(self, role_id: int, provider_id: int) -> None:
        """Remove single provider from role scope (idempotent)."""
        await self.db.execute(
            delete(RoleScopeProvider).where(
                RoleScopeProvider.role_id == role_id,
                RoleScopeProvider.provider_id == provider_id,
            )
        )
        await self.db.commit()
        logger.debug(
            "remove_role_scope_provider: role_id=%s, provider_id=%s",
            role_id,
            provider_id,
        )

    # ------------------------------------------------------------------
    # Effective scope + access checks
    # ------------------------------------------------------------------

    async def get_user_effective_scope(self, user_id: int) -> dict[str, set[int] | None]:
        """
        Return effective scope for user = UNION of all scopes from all user's roles.

        Returns ``{"source_group_ids": {1,2,3}, "credential_ids": {5,6},
        "sync_group_ids": {10,11}, "team_ids": {1,2}, "provider_ids": {7,8}}``.

        ``team_ids`` is computed from ``team_members`` membership (12.2.3) rather
        than a role-scope link table. Admins get None values (meaning "all access").
        """
        # Load user with roles → scopes in a single query
        user_result = await self.db.execute(
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.source_group_scopes),
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.credential_scopes),
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.sync_group_scopes),
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.provider_scopes),
            )
            .where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()

        if user is None:
            raise ValueError(f"User with id={user_id} not found")

        # Check if user has admin role
        is_admin = any(ur.role is not None and ur.role.name == "admin" for ur in user.user_roles)

        if is_admin:
            # Admins have unlimited access → None means "all"
            return {
                "source_group_ids": None,
                "credential_ids": None,
                "sync_group_ids": None,
                "team_ids": None,
                "provider_ids": None,
            }

        source_group_ids: set[int] = set()
        credential_ids: set[int] = set()
        sync_group_ids: set[int] = set()
        provider_ids: set[int] = set()

        for user_role in user.user_roles:
            role = user_role.role
            if role is None:
                continue

            for scope in role.source_group_scopes:
                source_group_ids.add(scope.source_group_id)

            for scope in role.credential_scopes:
                credential_ids.add(scope.credential_id)

            for scope in role.sync_group_scopes:
                sync_group_ids.add(scope.sync_group_id)

            for scope in role.provider_scopes:
                provider_ids.add(scope.provider_id)

        # team_ids = teams where the user is a member (12.2.3)
        team_result = await self.db.execute(
            select(TeamMember.team_id).where(TeamMember.user_id == user_id)
        )
        team_ids: set[int] = {row.team_id for row in team_result}

        return {
            "source_group_ids": source_group_ids,
            "credential_ids": credential_ids,
            "sync_group_ids": sync_group_ids,
            "team_ids": team_ids,
            "provider_ids": provider_ids,
        }

    async def check_scope_access(
        self,
        user_id: int,
        resource_type: str,
        resource_id: int,
    ) -> bool:
        """
        Check if user has access to specific resource through role scoping.

        Returns True if user is admin OR resource_id ∈ user's effective scope
        for that resource_type.
        """
        effective_scope = await self.get_user_effective_scope(user_id)

        id_set = effective_scope.get(f"{resource_type}_ids")
        # None means admin → all access
        if id_set is None:
            return True

        # set (possibly empty) → check membership
        return resource_id in id_set

    async def is_team_lead(self, user_id: int, team_id: int) -> bool:
        """Return True if ``user_id`` is the lead of ``team_id`` (12.2.3)."""
        result = await self.db.execute(
            select(TeamMember.role).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        role = result.scalar_one_or_none()
        return role is not None and role == TeamRole.lead
