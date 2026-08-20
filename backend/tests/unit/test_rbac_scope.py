"""
@file test_rbac_scope.py
@description Unit tests for RBACService scope management methods and
             Admin API scope endpoints — source groups, credentials,
             sync groups, effective scope, and scope-based access checks.
@dependencies pytest, pytest-asyncio, sqlalchemy, httpx
@relatedFiles ../../app/services/rbac_service.py, ../../app/api/admin.py,
              ../../app/models/role_scope.py
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RoleNotFoundError
from app.core.security import get_password_hash
from app.models.credential import Credential, CredentialType
from app.models.gitlab_project import GitlabProject, GitlabProjectType
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.models.role import Role, UserRole
from app.models.role_scope import (
    RoleScopeCredential,
    RoleScopeGitlabProject,
    RoleScopeProvider,
    RoleScopeSourceGroup,
    RoleScopeSyncGroup,
)
from app.models.source_group import SourceGroup
from app.models.sync_group import SyncGroup
from app.models.user import User
from app.services.rbac_service import RBACService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_role(db: AsyncSession, name: str = "test-role-scope") -> Role:
    """Create a custom test role."""
    role = Role(name=name, description="Test role for scope tests", is_custom=True)
    db.add(role)
    await db.commit()
    await db.refresh(role)
    return role


async def _seed_source_provider_and_group(
    db: AsyncSession, group_name: str = "test-org", external_id: str = "testorg"
) -> tuple[ResourceProvider, SourceGroup]:
    """Create a minimal ResourceProvider and SourceGroup for scope tests."""
    from app.core.secrets import encrypt_secret

    cred = Credential(
        name=f"cred-{group_name}",
        credential_type=CredentialType.github_token,
        provider="github",
        encrypted_secret=encrypt_secret("ghp_test_scope_token"),
    )
    db.add(cred)
    await db.flush()

    sp = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.github,
        category=ProviderCategory.public,
        direction=ProviderDirection.external,
        name=f"test-provider-{group_name}",
        label=f"test-provider-{group_name}",
        credential_id=cred.id,
    )
    db.add(sp)
    await db.flush()

    sg = SourceGroup(
        external_id=external_id,
        name=group_name,
        full_path=external_id,
    )
    db.add(sg)
    await db.commit()
    await db.refresh(sg)
    return sp, sg


async def _seed_credential(db: AsyncSession, name: str = "test-cred-scope") -> Credential:
    """Create a minimal Credential."""
    from app.core.secrets import encrypt_secret

    cred = Credential(
        name=name,
        credential_type=CredentialType.github_token,
        provider="github",
        encrypted_secret=encrypt_secret("ghp_test_scope_cred"),
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


async def _seed_sync_group(db: AsyncSession, name: str = "test-sync-group-scope") -> SyncGroup:
    """Create a minimal SyncGroup."""
    sg = SyncGroup(name=name, description="Test sync group for scope")
    db.add(sg)
    await db.commit()
    await db.refresh(sg)
    return sg


async def _seed_provider(db: AsyncSession, name: str = "test-provider-scope") -> ResourceProvider:
    """Create a minimal private ResourceProvider."""
    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.gitlab,
        category=ProviderCategory.private,
        direction=ProviderDirection.external,
        name=name,
        label=name,
        owner_user_id=999,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


async def _seed_gitlab_project(
    db: AsyncSession, provider: ResourceProvider, name: str = "test-gitlab-project"
) -> GitlabProject:
    """Create a minimal GitlabProject linked to *provider*."""
    project = GitlabProject(
        name=name,
        path=name,
        namespace_path="bigbug-mirrors",
        full_path=f"bigbug-mirrors/{name}",
        project_type=GitlabProjectType.components,
        provider_id=provider.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def _seed_user(
    db: AsyncSession,
    username: str = "testscopeuser",
    role: Role | None = None,
) -> User:
    """Create a user, optionally assigning a role."""
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    if role is not None:
        db.add(UserRole(user_id=user.id, role_id=role.id))

    await db.commit()
    await db.refresh(user)
    return user


# ========================================================================
# RBACService scope management tests
# ========================================================================


class TestRBACServiceSourceGroups:
    """Tests for RBACService source group scope methods."""

    @pytest.mark.asyncio
    async def test_get_role_scope_source_groups_empty(self, db_session: AsyncSession):
        """Getting scope for role with no source groups returns empty list."""
        role = await _seed_role(db_session, "empty-sg-role")
        service = RBACService(db_session)

        ids = await service.get_role_scope_source_groups(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_set_role_scope_source_groups(self, db_session: AsyncSession):
        """Setting source group scope for a role atomically replaces existing scope."""
        role = await _seed_role(db_session, "sg-set-role")
        _, sg1 = await _seed_source_provider_and_group(db_session, "org-a", "org-a")
        _, sg2 = await _seed_source_provider_and_group(db_session, "org-b", "org-b")
        service = RBACService(db_session)

        # Set initial scope
        await service.set_role_scope_source_groups(role.id, [sg1.id])
        ids = await service.get_role_scope_source_groups(role.id)
        assert ids == [sg1.id]

        # Atomically replace
        await service.set_role_scope_source_groups(role.id, [sg1.id, sg2.id])
        ids = await service.get_role_scope_source_groups(role.id)
        assert sorted(ids) == sorted([sg1.id, sg2.id])

        # Set empty to clear
        await service.set_role_scope_source_groups(role.id, [])
        ids = await service.get_role_scope_source_groups(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_add_role_scope_source_group_idempotent(self, db_session: AsyncSession):
        """Adding same source group twice is idempotent."""
        role = await _seed_role(db_session, "sg-add-role")
        _, sg = await _seed_source_provider_and_group(db_session, "idem-org", "idem-org")
        service = RBACService(db_session)

        await service.add_role_scope_source_group(role.id, sg.id)
        ids = await service.get_role_scope_source_groups(role.id)
        assert ids == [sg.id]

        # Add again — idempotent, no error
        await service.add_role_scope_source_group(role.id, sg.id)
        ids = await service.get_role_scope_source_groups(role.id)
        assert ids == [sg.id]

    @pytest.mark.asyncio
    async def test_remove_role_scope_source_group_idempotent(self, db_session: AsyncSession):
        """Removing a non-existent source group scope is idempotent (no error)."""
        role = await _seed_role(db_session, "sg-remove-role")
        service = RBACService(db_session)

        # Removing non-existent — should not raise
        await service.remove_role_scope_source_group(role.id, 99999)

        # Verify still empty
        ids = await service.get_role_scope_source_groups(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_set_role_scope_nonexistent_role(self, db_session: AsyncSession):
        """Setting scope for non-existent role raises RoleNotFoundError."""
        service = RBACService(db_session)

        with pytest.raises(RoleNotFoundError, match="Role with id=99999 not found"):
            await service.set_role_scope_source_groups(99999, [1])


class TestRBACServiceCredentials:
    """Tests for RBACService credential scope methods."""

    @pytest.mark.asyncio
    async def test_get_role_scope_credentials_empty(self, db_session: AsyncSession):
        """Getting credential scope for role with none returns empty list."""
        role = await _seed_role(db_session, "cred-empty-role")
        service = RBACService(db_session)

        ids = await service.get_role_scope_credentials(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_set_role_scope_credentials(self, db_session: AsyncSession):
        """Setting credential scope atomically replaces existing ones."""
        role = await _seed_role(db_session, "cred-set-role")
        cred1 = await _seed_credential(db_session, "cred-a")
        cred2 = await _seed_credential(db_session, "cred-b")
        service = RBACService(db_session)

        await service.set_role_scope_credentials(role.id, [cred1.id])
        ids = await service.get_role_scope_credentials(role.id)
        assert ids == [cred1.id]

        # Replace
        await service.set_role_scope_credentials(role.id, [cred1.id, cred2.id])
        ids = await service.get_role_scope_credentials(role.id)
        assert sorted(ids) == sorted([cred1.id, cred2.id])

        # Clear
        await service.set_role_scope_credentials(role.id, [])
        ids = await service.get_role_scope_credentials(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_credential_scope_nonexistent_role(self, db_session: AsyncSession):
        """Setting credential scope for non-existent role raises RoleNotFoundError."""
        service = RBACService(db_session)

        with pytest.raises(RoleNotFoundError, match="Role with id=99999 not found"):
            await service.set_role_scope_credentials(99999, [1])


class TestRBACServiceSyncGroups:
    """Tests for RBACService sync group scope methods."""

    @pytest.mark.asyncio
    async def test_get_role_scope_sync_groups_empty(self, db_session: AsyncSession):
        """Getting sync group scope for role with none returns empty list."""
        role = await _seed_role(db_session, "sync-empty-role")
        service = RBACService(db_session)

        ids = await service.get_role_scope_sync_groups(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_set_role_scope_sync_groups(self, db_session: AsyncSession):
        """Setting sync group scope atomically replaces existing ones."""
        role = await _seed_role(db_session, "sync-set-role")
        sg1 = await _seed_sync_group(db_session, "sync-a")
        service = RBACService(db_session)

        await service.set_role_scope_sync_groups(role.id, [sg1.id])
        ids = await service.get_role_scope_sync_groups(role.id)
        assert ids == [sg1.id]

        # Atomic replace — clear
        await service.set_role_scope_sync_groups(role.id, [])
        ids = await service.get_role_scope_sync_groups(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_sync_group_scope_nonexistent_role(self, db_session: AsyncSession):
        """Setting sync group scope for non-existent role raises RoleNotFoundError."""
        service = RBACService(db_session)

        with pytest.raises(RoleNotFoundError, match="Role with id=99999 not found"):
            await service.set_role_scope_sync_groups(99999, [1])


class TestRBACServiceProviders:
    """Tests for RBACService provider scope methods."""

    @pytest.mark.asyncio
    async def test_get_role_scope_providers_empty(self, db_session: AsyncSession):
        """Getting provider scope for role with none returns empty list."""
        role = await _seed_role(db_session, "provider-empty-role")
        service = RBACService(db_session)

        ids = await service.get_role_scope_providers(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_set_role_scope_providers(self, db_session: AsyncSession):
        """Setting provider scope atomically replaces existing ones."""
        role = await _seed_role(db_session, "provider-set-role")
        p1 = await _seed_provider(db_session, "provider-a")
        p2 = await _seed_provider(db_session, "provider-b")
        service = RBACService(db_session)

        await service.set_role_scope_providers(role.id, [p1.id])
        ids = await service.get_role_scope_providers(role.id)
        assert ids == [p1.id]

        await service.set_role_scope_providers(role.id, [p1.id, p2.id])
        ids = await service.get_role_scope_providers(role.id)
        assert sorted(ids) == sorted([p1.id, p2.id])

        await service.set_role_scope_providers(role.id, [])
        ids = await service.get_role_scope_providers(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_add_role_scope_provider_idempotent(self, db_session: AsyncSession):
        """Adding the same provider twice is idempotent."""
        role = await _seed_role(db_session, "provider-add-role")
        p = await _seed_provider(db_session, "provider-idem")
        service = RBACService(db_session)

        await service.add_role_scope_provider(role.id, p.id)
        ids = await service.get_role_scope_providers(role.id)
        assert ids == [p.id]

        await service.add_role_scope_provider(role.id, p.id)
        ids = await service.get_role_scope_providers(role.id)
        assert ids == [p.id]

    @pytest.mark.asyncio
    async def test_remove_role_scope_provider_idempotent(self, db_session: AsyncSession):
        """Removing a non-existent provider scope is idempotent (no error)."""
        role = await _seed_role(db_session, "provider-remove-role")
        service = RBACService(db_session)

        await service.remove_role_scope_provider(role.id, 99999)

        ids = await service.get_role_scope_providers(role.id)
        assert ids == []

    @pytest.mark.asyncio
    async def test_provider_scope_nonexistent_role(self, db_session: AsyncSession):
        """Setting provider scope for non-existent role raises RoleNotFoundError."""
        service = RBACService(db_session)

        with pytest.raises(RoleNotFoundError, match="Role with id=99999 not found"):
            await service.set_role_scope_providers(99999, [1])


# ========================================================================
# Effective scope tests
# ========================================================================


class TestEffectiveScope:
    """Tests for RBACService.get_user_effective_scope()."""

    @pytest.mark.asyncio
    async def test_get_user_effective_scope_no_roles(self, db_session: AsyncSession):
        """User with no roles has empty effective scope."""
        user = await _seed_user(db_session, "noroles")
        service = RBACService(db_session)

        scope = await service.get_user_effective_scope(user.id)
        assert scope["source_group_ids"] == set()
        assert scope["credential_ids"] == set()
        assert scope["sync_group_ids"] == set()
        assert scope["team_ids"] == set()

    @pytest.mark.asyncio
    async def test_get_user_effective_scope_with_scope(self, db_session: AsyncSession):
        """User with scoped role gets union of all scope resources."""
        role = await _seed_role(db_session, "scoped-role")
        _, sg = await _seed_source_provider_and_group(db_session, "eff-org", "eff-org")
        sync_g = await _seed_sync_group(db_session, "eff-sync")
        cred = await _seed_credential(db_session, "eff-cred")
        provider = await _seed_provider(db_session, "eff-provider")

        # Add scope to the role
        db_session.add(RoleScopeSourceGroup(role_id=role.id, source_group_id=sg.id))
        db_session.add(RoleScopeSyncGroup(role_id=role.id, sync_group_id=sync_g.id))
        db_session.add(RoleScopeCredential(role_id=role.id, credential_id=cred.id))
        db_session.add(RoleScopeProvider(role_id=role.id, provider_id=provider.id))
        await db_session.commit()

        user = await _seed_user(db_session, "scopeduser", role=role)
        service = RBACService(db_session)

        scope = await service.get_user_effective_scope(user.id)
        assert scope["source_group_ids"] == {sg.id}
        assert scope["credential_ids"] == {cred.id}
        assert scope["sync_group_ids"] == {sync_g.id}
        assert scope["provider_ids"] == {provider.id}
        assert scope["team_ids"] == set()

    @pytest.mark.asyncio
    async def test_get_user_effective_scope_gitlab_projects(self, db_session: AsyncSession):
        """User with a gitlab-project-scoped role gets the union of project ids."""
        role = await _seed_role(db_session, "gitlab-project-role")
        provider = await _seed_provider(db_session, "gitlab-project-provider")
        project = await _seed_gitlab_project(db_session, provider, "scoped-components")

        db_session.add(RoleScopeGitlabProject(role_id=role.id, gitlab_project_id=project.id))
        await db_session.commit()

        user = await _seed_user(db_session, "gitlab-project-user", role=role)
        service = RBACService(db_session)

        scope = await service.get_user_effective_scope(user.id)
        assert scope["gitlab_project_ids"] == {project.id}

    @pytest.mark.asyncio
    async def test_get_user_effective_scope_admin(self, db_session: AsyncSession):
        """Admin user gets None values (meaning all access)."""
        # Get existing admin role (from conftest fixtures), or create
        result = await db_session.execute(select(Role).where(Role.name == "admin"))
        admin_role = result.scalar_one_or_none()
        if admin_role is None:
            admin_role = Role(name="admin", description="Administrator")
            db_session.add(admin_role)
            await db_session.commit()

        user = await _seed_user(db_session, "admin-scope-user", role=admin_role)
        service = RBACService(db_session)

        scope = await service.get_user_effective_scope(user.id)
        assert scope["source_group_ids"] is None
        assert scope["credential_ids"] is None
        assert scope["sync_group_ids"] is None
        assert scope["team_ids"] is None

    @pytest.mark.asyncio
    async def test_get_user_effective_scope_multiple_roles(self, db_session: AsyncSession):
        """User with multiple roles gets union of all scopes."""
        role_a = await _seed_role(db_session, "multi-role-a")
        role_b = await _seed_role(db_session, "multi-role-b")
        _, sg1 = await _seed_source_provider_and_group(db_session, "multi-org-1", "multi-org-1")
        _, sg2 = await _seed_source_provider_and_group(db_session, "multi-org-2", "multi-org-2")

        # Role A has sg1, Role B has sg2
        db_session.add(RoleScopeSourceGroup(role_id=role_a.id, source_group_id=sg1.id))
        db_session.add(RoleScopeSourceGroup(role_id=role_b.id, source_group_id=sg2.id))
        await db_session.commit()

        # User gets both roles
        user = User(
            username="multirole",
            email="multirole@test.com",
            hashed_password=get_password_hash("testpassword"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        db_session.add(UserRole(user_id=user.id, role_id=role_a.id))
        db_session.add(UserRole(user_id=user.id, role_id=role_b.id))
        await db_session.commit()

        service = RBACService(db_session)
        scope = await service.get_user_effective_scope(user.id)
        assert scope["source_group_ids"] == {sg1.id, sg2.id}


# ========================================================================
# Scope access check tests
# ========================================================================


class TestCheckScopeAccess:
    """Tests for RBACService.check_scope_access()."""

    @pytest.mark.asyncio
    async def test_check_scope_access_admin_always_true(self, db_session: AsyncSession):
        """Admin always has access regardless of scope."""
        result = await db_session.execute(select(Role).where(Role.name == "admin"))
        admin_role = result.scalar_one_or_none()
        if admin_role is None:
            admin_role = Role(name="admin", description="Administrator")
            db_session.add(admin_role)
            await db_session.commit()

        user = await _seed_user(db_session, "admin-access-user", role=admin_role)
        service = RBACService(db_session)

        # Admin should have access to any resource, even nonexistent
        assert await service.check_scope_access(user.id, "source_group", 99999) is True
        assert await service.check_scope_access(user.id, "credential", 1) is True
        assert await service.check_scope_access(user.id, "sync_group", 5) is True

    @pytest.mark.asyncio
    async def test_check_scope_access_with_scope_allows(self, db_session: AsyncSession):
        """User with resource in scope gets True."""
        role = await _seed_role(db_session, "access-role")
        _, sg = await _seed_source_provider_and_group(db_session, "access-org", "access-org")

        db_session.add(RoleScopeSourceGroup(role_id=role.id, source_group_id=sg.id))
        await db_session.commit()

        user = await _seed_user(db_session, "accessuser", role=role)
        service = RBACService(db_session)

        assert await service.check_scope_access(user.id, "source_group", sg.id) is True

    @pytest.mark.asyncio
    async def test_check_scope_access_without_scope_denies(self, db_session: AsyncSession):
        """User without resource in scope gets False."""
        role = await _seed_role(db_session, "deny-role")
        _, sg = await _seed_source_provider_and_group(db_session, "deny-org", "deny-org")

        # Role has scope for sg, but we check a different resource
        db_session.add(RoleScopeSourceGroup(role_id=role.id, source_group_id=sg.id))
        await db_session.commit()

        user = await _seed_user(db_session, "denyuser", role=role)
        service = RBACService(db_session)

        assert await service.check_scope_access(user.id, "source_group", sg.id + 999) is False

    @pytest.mark.asyncio
    async def test_check_scope_access_gitlab_project(self, db_session: AsyncSession):
        """check_scope_access works for the ``gitlab_project`` resource type."""
        role = await _seed_role(db_session, "gitlab-project-access-role")
        provider = await _seed_provider(db_session, "gitlab-project-access-provider")
        project = await _seed_gitlab_project(db_session, provider, "access-components")

        db_session.add(RoleScopeGitlabProject(role_id=role.id, gitlab_project_id=project.id))
        await db_session.commit()

        user = await _seed_user(db_session, "gitlab-project-access-user", role=role)
        service = RBACService(db_session)

        assert await service.check_scope_access(user.id, "gitlab_project", project.id) is True
        assert (
            await service.check_scope_access(user.id, "gitlab_project", project.id + 999) is False
        )

    @pytest.mark.asyncio
    async def test_check_scope_access_no_roles(self, db_session: AsyncSession):
        """User with no roles gets False."""
        user = await _seed_user(db_session, "noroles-access")
        service = RBACService(db_session)

        assert await service.check_scope_access(user.id, "source_group", 1) is False
        assert await service.check_scope_access(user.id, "credential", 1) is False
        assert await service.check_scope_access(user.id, "sync_group", 1) is False
        assert await service.check_scope_access(user.id, "gitlab_project", 1) is False


# ========================================================================
# Admin API scope endpoint tests
# ========================================================================


class TestAdminScopeAPI:
    """Test admin scope API endpoints."""

    @pytest.mark.asyncio
    async def test_get_scope_source_groups_as_admin(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can get role scope source groups — 200."""
        role = await _seed_role(db_session, "api-sg-role")
        _, sg = await _seed_source_provider_and_group(db_session, "api-org", "api-org")

        # Set scope for role
        db_session.add(RoleScopeSourceGroup(role_id=role.id, source_group_id=sg.id))
        await db_session.commit()

        response = await client.get(
            f"/api/admin/roles/{role.id}/scopes/source-groups",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert sg.id in data["source_group_ids"]

    @pytest.mark.asyncio
    async def test_get_scope_source_groups_as_non_admin(
        self, db_session: AsyncSession, client: AsyncClient, operator_token: str
    ):
        """Non-admin gets 403."""
        role = await _seed_role(db_session, "api-sg-role-na")
        _, sg = await _seed_source_provider_and_group(db_session, "api-org-na", "api-org-na")
        db_session.add(RoleScopeSourceGroup(role_id=role.id, source_group_id=sg.id))
        await db_session.commit()

        response = await client.get(
            f"/api/admin/roles/{role.id}/scopes/source-groups",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_put_scope_source_groups(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can update scope source groups — 200."""
        role = await _seed_role(db_session, "api-put-sg-role")
        _, sg1 = await _seed_source_provider_and_group(db_session, "put-org-1", "put-org-1")
        _, sg2 = await _seed_source_provider_and_group(db_session, "put-org-2", "put-org-2")

        response = await client.put(
            f"/api/admin/roles/{role.id}/scopes/source-groups",
            json={"source_group_ids": [sg1.id, sg2.id]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert sorted(data["source_group_ids"]) == sorted([sg1.id, sg2.id])

    @pytest.mark.asyncio
    async def test_post_scope_item(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can add a single scope item — 201."""
        role = await _seed_role(db_session, "api-post-role")
        _, sg = await _seed_source_provider_and_group(db_session, "post-org", "post-org")

        response = await client.post(
            f"/api/admin/roles/{role.id}/scopes/source-groups",
            json={"source_group_id": sg.id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert sg.id in data["source_group_ids"]

        # Add same again — idempotent (should still return 201 with the item)
        response = await client.post(
            f"/api/admin/roles/{role.id}/scopes/source-groups",
            json={"source_group_id": sg.id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        assert sg.id in response.json()["source_group_ids"]

    @pytest.mark.asyncio
    async def test_delete_scope_item(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can remove a scope item — 204."""
        role = await _seed_role(db_session, "api-del-role")
        _, sg = await _seed_source_provider_and_group(db_session, "del-org", "del-org")

        # First add
        db_session.add(RoleScopeSourceGroup(role_id=role.id, source_group_id=sg.id))
        await db_session.commit()

        response = await client.delete(
            f"/api/admin/roles/{role.id}/scopes/source-groups/{sg.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204
        assert response.content == b""

        # Verify removed
        get_resp = await client.get(
            f"/api/admin/roles/{role.id}/scopes/source-groups",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = get_resp.json()
        assert sg.id not in data["source_group_ids"]

    @pytest.mark.asyncio
    async def test_get_scope_credentials(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can get credential scope — 200."""
        role = await _seed_role(db_session, "api-cred-role")
        cred = await _seed_credential(db_session, "api-cred")

        db_session.add(RoleScopeCredential(role_id=role.id, credential_id=cred.id))
        await db_session.commit()

        response = await client.get(
            f"/api/admin/roles/{role.id}/scopes/credentials",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert cred.id in data["credential_ids"]

    @pytest.mark.asyncio
    async def test_get_scope_sync_groups(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can get sync group scope — 200."""
        role = await _seed_role(db_session, "api-sync-role")
        sg = await _seed_sync_group(db_session, "api-sync")

        db_session.add(RoleScopeSyncGroup(role_id=role.id, sync_group_id=sg.id))
        await db_session.commit()

        response = await client.get(
            f"/api/admin/roles/{role.id}/scopes/sync-groups",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert sg.id in data["sync_group_ids"]

    @pytest.mark.asyncio
    async def test_get_scope_providers(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can get provider scope — 200."""
        role = await _seed_role(db_session, "api-provider-role")
        provider = await _seed_provider(db_session, "api-provider")

        db_session.add(RoleScopeProvider(role_id=role.id, provider_id=provider.id))
        await db_session.commit()

        response = await client.get(
            f"/api/admin/roles/{role.id}/scopes/providers",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert provider.id in data["provider_ids"]

    @pytest.mark.asyncio
    async def test_put_scope_providers(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can replace provider scope atomically — 200."""
        role = await _seed_role(db_session, "api-put-provider-role")
        p1 = await _seed_provider(db_session, "put-provider-1")
        p2 = await _seed_provider(db_session, "put-provider-2")

        response = await client.put(
            f"/api/admin/roles/{role.id}/scopes/providers",
            json={"provider_ids": [p1.id, p2.id]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert sorted(data["provider_ids"]) == sorted([p1.id, p2.id])

    @pytest.mark.asyncio
    async def test_post_scope_provider(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can add a single provider scope item — 201."""
        role = await _seed_role(db_session, "api-post-provider-role")
        provider = await _seed_provider(db_session, "post-provider")

        response = await client.post(
            f"/api/admin/roles/{role.id}/scopes/providers",
            json={"provider_id": provider.id},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert provider.id in data["provider_ids"]

    @pytest.mark.asyncio
    async def test_delete_scope_provider(
        self, db_session: AsyncSession, client: AsyncClient, admin_token: str
    ):
        """Admin can remove a single provider scope item — 204."""
        role = await _seed_role(db_session, "api-del-provider-role")
        provider = await _seed_provider(db_session, "del-provider")

        db_session.add(RoleScopeProvider(role_id=role.id, provider_id=provider.id))
        await db_session.commit()

        response = await client.delete(
            f"/api/admin/roles/{role.id}/scopes/providers/{provider.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204
        assert response.content == b""

        get_resp = await client.get(
            f"/api/admin/roles/{role.id}/scopes/providers",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert provider.id not in get_resp.json()["provider_ids"]

    @pytest.mark.asyncio
    async def test_scope_for_nonexistent_role_returns_404(
        self, client: AsyncClient, admin_token: str
    ):
        """PUT scope for non-existent role returns 404."""
        response = await client.put(
            "/api/admin/roles/99999/scopes/source-groups",
            json={"source_group_ids": [1]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthorized_scope_access(self, client: AsyncClient):
        """Unauthorized request returns 401."""
        response = await client.get("/api/admin/roles/1/scopes/source-groups")
        # No auth header — should be 401 or 403
        assert response.status_code in (401, 403)
