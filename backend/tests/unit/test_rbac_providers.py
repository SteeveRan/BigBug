"""
@file test_rbac_providers.py
@description Unit tests for Providers V3 RBAC (stage 11, section 11.3.2 / 6.2):
              permission matrix × categories, role_scope_providers granting access
              to another user's private provider, and the phase-5 legacy-permission
              cleanup (seed_admin.py distribution + migration removal list).
@dependencies backend/app/services/rbac_service.py, backend/app/services/providers/service.py,
             backend/docker/seed_admin.py, backend/alembic/versions/20260815_0000_*.py
"""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.core.security import get_password_hash
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.models.role import Role, UserRole
from app.models.role_scope import RoleScopeProvider
from app.models.user import User
from app.services.providers.service import ProviderService
from app.services.rbac_service import RBACService

BACKEND_DIR = Path(__file__).resolve().parents[2]
SEED_ADMIN_PATH = BACKEND_DIR / "docker" / "seed_admin.py"
MIGRATION_PATH = next(
    (BACKEND_DIR / "alembic" / "versions").glob("20260815_0000_*_remove_legacy_permissions.py")
)
SEED_PERMISSIONS_MIGRATION_PATH = next(
    (BACKEND_DIR / "alembic" / "versions").glob(
        "20260815_1108_*_seed_providers_teams_permissions.py"
    )
)

# Legacy permissions that phase 5 removes (section 6.2).
LEGACY_PERMISSIONS = {
    "credentials:use",
    "integrations:read",
    "integrations:write",
    "integrations:manage",
    "docker_registry:manage",
    "helm_repository:manage",
    "pipelines:manage",
}


def _load_seed_admin():
    spec = importlib.util.spec_from_file_location("seed_admin", SEED_ADMIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_phase5", MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_seed_permissions_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migration_seed_providers_teams", SEED_PERMISSIONS_MIGRATION_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _user(user_id: int, permissions: list[str]) -> User:
    user = User(username=f"u{user_id}", email=f"u{user_id}@test.com")
    user.id = user_id
    user._cached_permissions = permissions
    return user


ADMIN = [
    "providers:read",
    "providers:write",
    "providers:delete",
    "providers:use",
    "providers:read_all",
    "providers_system:write",
]
OPERATOR = ["providers:read", "providers:write", "providers:use"]


# ========================================================================
# Seed distribution (seed_admin.py) — 6.1 / 6.2
# ========================================================================


class TestSeedAdminDistribution:
    def test_admin_has_all_provider_and_team_permissions(self):
        mod = _load_seed_admin()
        admin = set(mod.ADMIN_PERMISSIONS)
        for perm in [
            "providers:read",
            "providers:write",
            "providers:delete",
            "providers:use",
            "providers:read_all",
            "providers_system:write",
            "providers:share",
            "teams:read",
            "teams:write",
            "teams:manage_members",
            "credentials:read",
            "credentials:write",
        ]:
            assert perm in admin

    def test_operator_has_no_mutation_or_system_or_team_admin(self):
        mod = _load_seed_admin()
        op = set(mod.OPERATOR_PERMISSIONS)
        assert "providers:read" in op
        assert "providers:write" in op
        assert "providers:use" in op
        assert "providers:share" in op
        assert "teams:read" in op
        for forbidden in [
            "providers:delete",
            "providers:read_all",
            "providers_system:write",
            "teams:write",
            "teams:manage_members",
        ]:
            assert forbidden not in op

    def test_viewer_read_only(self):
        mod = _load_seed_admin()
        viewer = set(mod.VIEWER_PERMISSIONS)
        assert "providers:read" in viewer
        assert "teams:read" in viewer
        for forbidden in [
            "providers:write",
            "providers:delete",
            "providers:use",
            "providers:share",
            "providers:read_all",
            "providers_system:write",
            "teams:write",
            "teams:manage_members",
            "credentials:write",
        ]:
            assert forbidden not in viewer

    def test_no_legacy_permissions_assigned(self):
        mod = _load_seed_admin()
        all_assigned = (
            set(mod.ADMIN_PERMISSIONS) | set(mod.OPERATOR_PERMISSIONS) | set(mod.VIEWER_PERMISSIONS)
        )
        assert all_assigned.isdisjoint(LEGACY_PERMISSIONS)

    def test_provider_team_permissions_are_seeded_by_migration(self):
        """Every providers/teams/credentials:write permission declared in
        seed_admin.py must actually be inserted by the seeding migration
        (20260815_1108_0cce18c6c867). This catches the root-cause bug: the
        lists existed in seed_admin.py but were never written to the DB."""
        mod = _load_seed_admin()
        migration = _load_seed_permissions_migration_module()

        seeded_by_migration = {p["name"] for p in migration.NEW_PERMISSIONS}

        expected = {
            "providers:read",
            "providers:write",
            "providers:delete",
            "providers:use",
            "providers:read_all",
            "providers_system:write",
            "providers:share",
            "teams:read",
            "teams:write",
            "teams:manage_members",
            "credentials:write",
        }
        assert seeded_by_migration == expected

        # Admin must receive every one of them.
        assert expected <= set(mod.ADMIN_PERMISSIONS)

    def test_migration_role_assignments_match_seed_admin(self):
        """The migration's per-role assignment lists are subsets of the
        corresponding seed_admin.py role lists (no phantom permissions)."""
        mod = _load_seed_admin()
        migration = _load_seed_permissions_migration_module()

        assert set(migration.ADMIN_NEW_PERMISSIONS) <= set(mod.ADMIN_PERMISSIONS)
        assert set(migration.OPERATOR_NEW_PERMISSIONS) <= set(mod.OPERATOR_PERMISSIONS)
        assert set(migration.VIEWER_NEW_PERMISSIONS) <= set(mod.VIEWER_PERMISSIONS)


# ========================================================================
# role_scope_providers — 6.3
# ========================================================================


class TestRoleScopeProviderAccess:
    async def _seed_role_and_provider(self, db: AsyncSession) -> tuple[Role, ResourceProvider]:
        role = Role(name="provider-scope-role", description="scoped", is_custom=True)
        db.add(role)
        await db.flush()

        provider = ResourceProvider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="someone-elses-provider",
            label="Someone Else",
            owner_user_id=999,  # owned by another user
        )
        db.add(provider)
        await db.flush()
        return role, provider

    async def _seed_scoped_user(self, db: AsyncSession, role: Role) -> User:
        user = User(
            username="provider-scope-user",
            email="provider-scope-user@test.com",
            hashed_password=get_password_hash("testpassword"),
            is_active=True,
        )
        db.add(user)
        await db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        await db.commit()
        await db.refresh(user)
        return user

    async def test_provider_scope_grants_access_to_others_private(self, db_session: AsyncSession):
        role, provider = await self._seed_role_and_provider(db_session)
        db_session.add(RoleScopeProvider(role_id=role.id, provider_id=provider.id))
        await db_session.commit()

        user = await self._seed_scoped_user(db_session, role)
        scope = await RBACService(db_session).get_user_effective_scope(user.id)
        assert provider.id in scope["provider_ids"]
        assert (
            await RBACService(db_session).check_scope_access(user.id, "provider", provider.id)
            is True
        )

    async def test_provider_scope_denies_without_link(self, db_session: AsyncSession):
        role, provider = await self._seed_role_and_provider(db_session)
        await db_session.commit()

        user = await self._seed_scoped_user(db_session, role)
        assert (
            await RBACService(db_session).check_scope_access(user.id, "provider", provider.id)
            is False
        )
        assert (
            await RBACService(db_session).check_scope_access(user.id, "provider", provider.id + 999)
            is False
        )


# ========================================================================
# Permission × category matrix — 11.3.2
# ========================================================================


class TestProviderCategoryMatrix:
    async def test_system_create_requires_providers_system_write(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        with pytest.raises(DomainError) as exc:
            await svc.create_provider(
                domain=ProviderDomain.git,
                subtype=ProviderSubtype.gitlab,
                category=ProviderCategory.system,
                direction=ProviderDirection.internal,
                name="sys-gitlab",
                label="Sys GitLab",
                user=_user(7, OPERATOR),
            )
        assert "providers_system:write" in str(exc.value)

    async def test_system_create_allowed_for_admin(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        p = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.system,
            direction=ProviderDirection.internal,
            name="sys-gitlab-admin",
            label="Sys GitLab",
            user=_user(1, ADMIN),
        )
        assert p.id is not None

    async def test_private_read_denied_to_non_owner(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        provider = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="private-gh",
            label="Private GH",
            user=_user(7, OPERATOR),
        )
        # Another operator (id=8) without read_all cannot read it.
        with pytest.raises(DomainError) as exc:
            await svc.get_provider(provider.id, _user(8, OPERATOR))
        assert exc.value.status_code == 403

    async def test_private_read_allowed_to_read_all(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        provider = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="private-gh-2",
            label="Private GH 2",
            user=_user(7, OPERATOR),
        )
        fetched = await svc.get_provider(provider.id, _user(1, ADMIN))
        assert fetched.id == provider.id


# ========================================================================
# Migration removal list — 6.2
# ========================================================================


class TestLegacyPermissionMigration:
    def test_migration_removes_exactly_expected_legacy_permissions(self):
        mod = _load_migration_module()
        assert set(mod._LEGACY_PERMISSIONS.keys()) == LEGACY_PERMISSIONS

    def test_credentials_read_is_kept(self):
        mod = _load_migration_module()
        assert "credentials:read" not in mod._LEGACY_PERMISSIONS
