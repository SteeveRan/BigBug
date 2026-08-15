"""
@file e2e/conftest.py
@description E2E-test specific fixtures: ENCRYPTION_KEY mock + permission seeding
             for the admin role so that require_permission() checks pass.
@dependencies pytest, sqlalchemy, app.core.secrets, app.models
@relatedFiles ../conftest.py (root fixtures: client, admin_token, admin_role)
"""

from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import RoleName
from app.models.permission import Permission, role_permissions
from app.models.role import Role
from app.models.team import Team, TeamRole
from app.models.team_member import TeamMember
from app.models.user import User

# Valid Fernet key for tests (same as unit/conftest.py)
_VALID_FERNET_KEY = "Z0lZSjZpc3gyMDI1Y29vbHByb2plY3RmZXJuZXRrZXk="

# Permissions required by integration endpoints
REQUIRED_PERMISSIONS = [
    {"name": "integrations:manage", "description": "Manage GitLab, Harbor, GitHub instances"},
    {"name": "docker_registry:manage", "description": "Manage Docker Registry instances"},
    {"name": "helm_repository:manage", "description": "Manage Helm Repository instances"},
    {"name": "pipelines:read", "description": "Read pipeline runs"},
    {"name": "pipelines:write", "description": "Create and trigger pipelines"},
    {"name": "pipelines:delete", "description": "Cancel and delete pipelines"},
    {"name": "users:read", "description": "Read users and audit logs"},
]

# Providers V3 permissions, distributed per role (phase 2 RBAC, section 6.1).
# Admin: everything; Operator: read/write/use; Viewer: read only.
PROVIDER_PERMISSIONS_BY_ROLE = {
    RoleName.ADMIN.value: [
        "providers:read",
        "providers:write",
        "providers:delete",
        "providers:use",
        "providers:read_all",
        "providers_system:write",
        "providers:share",
    ],
    RoleName.OPERATOR.value: [
        "providers:read",
        "providers:write",
        "providers:use",
        "providers:share",
    ],
    RoleName.VIEWER.value: [
        "providers:read",
    ],
}

# Teams / sharing permissions (12.2.3), distributed per role.
TEAM_PERMISSIONS_BY_ROLE = {
    RoleName.ADMIN.value: [
        "teams:read",
        "teams:write",
        "teams:manage_members",
    ],
    RoleName.OPERATOR.value: [
        "teams:read",
    ],
    RoleName.VIEWER.value: [
        "teams:read",
    ],
}

# Domain resource permissions (docker/helm/images/projects) mirroring
# seed_admin.py so the operator/viewer e2e fixtures align with production roles.
# Admin is already fully seeded by root conftest's ``_ALL_PERMISSIONS``.
RESOURCE_PERMISSIONS_BY_ROLE = {
    RoleName.OPERATOR.value: [
        "mirrors:read",
        "mirrors:write",
        "mirrors:sync",
        "mirrors:import",
        "mirrors:integrity_check",
        "projects:read",
        "projects:write",
        "helm:read",
        "helm:write",
        "helm:sync",
        "helm:index",
        "docker:read",
        "docker:write",
        "docker:sync",
        "docker:index",
        "gold_images:read",
        "gold_images:write",
        "gold_images:build",
        "app_images:read",
        "app_images:write",
        "app_images:build",
        "pipelines:read",
        "pipelines:write",
        "source_groups:read",
        "source_groups:write",
        "source_groups:refresh",
        "sync_groups:read",
        "sync_groups:write",
        "audit:read",
    ],
    RoleName.VIEWER.value: [
        "mirrors:read",
        "projects:read",
        "helm:read",
        "docker:read",
        "gold_images:read",
        "app_images:read",
        "pipelines:read",
        "source_groups:read",
        "sync_groups:read",
        "audit:read",
    ],
}


@pytest.fixture(autouse=True)
def _patch_encryption_key():
    """Make encrypt_secret/decrypt_secret work in the e2e test environment."""
    with patch("app.core.secrets.settings") as mock_settings:
        mock_settings.encryption_key = _VALID_FERNET_KEY
        from app.core.secrets import get_cipher

        get_cipher.cache_clear()
        yield
        get_cipher.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def seeded_permissions(db_session: AsyncSession):
    """Ensure the three standard roles and their permissions exist.

    *Autouse* so permissions are present regardless of which fixtures a
    particular test happens to request — this is critical when tests that
    don't need ``admin_token`` run before tests that do, because the
    root conftest creates the roles *without* the extra e2e permissions.

    Set-based: build the full role→permission map once, then issue a handful
    of bulk queries instead of per-permission SELECT/flush/refresh round trips.
    """
    role_names = [RoleName.ADMIN.value, RoleName.OPERATOR.value, RoleName.VIEWER.value]

    # ── build the desired role→permission map ────────────────────────────
    permissions_by_role: dict[str, set[str]] = {name: set() for name in role_names}
    descriptions: dict[str, str] = {}

    for perm_data in REQUIRED_PERMISSIONS:
        permissions_by_role[RoleName.ADMIN.value].add(perm_data["name"])
        descriptions[perm_data["name"]] = perm_data["description"]

    for mapping in (
        PROVIDER_PERMISSIONS_BY_ROLE,
        TEAM_PERMISSIONS_BY_ROLE,
        RESOURCE_PERMISSIONS_BY_ROLE,
    ):
        for role_name, permission_names in mapping.items():
            permissions_by_role[role_name].update(permission_names)

    # ── ensure the three standard roles exist ──────────────────────────
    existing_roles = (
        (await db_session.execute(select(Role).where(Role.name.in_(role_names)))).scalars().all()
    )
    roles: dict[str, Role] = {r.name: r for r in existing_roles}
    for name in role_names:
        if name not in roles:
            role = Role(name=name, description=f"{name.capitalize()} role")
            db_session.add(role)
            await db_session.flush()
            roles[name] = role

    # ── ensure all referenced permissions exist (bulk create) ───────────
    all_permission_names = set().union(*permissions_by_role.values())
    existing_perms = (await db_session.execute(select(Permission))).scalars().all()
    perms_by_name: dict[str, Permission] = {p.name: p for p in existing_perms}

    new_perms = [
        Permission(name=name, description=descriptions.get(name, f"Auto-seeded: {name}"))
        for name in all_permission_names
        if name not in perms_by_name
    ]
    if new_perms:
        db_session.add_all(new_perms)
        await db_session.flush()
        for perm in new_perms:
            perms_by_name[perm.name] = perm

    # ── assign missing role→permission links (bulk insert) ──────────────
    role_ids = [roles[name].id for name in role_names]
    existing_links = (
        await db_session.execute(
            select(role_permissions.c.role_id, role_permissions.c.permission_id).where(
                role_permissions.c.role_id.in_(role_ids)
            )
        )
    ).all()
    existing_link_set = {(role_id, perm_id) for role_id, perm_id in existing_links}

    links_to_insert = [
        {"role_id": roles[role_name].id, "permission_id": perms_by_name[perm_name].id}
        for role_name in role_names
        for perm_name in permissions_by_role[role_name]
        if (roles[role_name].id, perms_by_name[perm_name].id) not in existing_link_set
    ]
    if links_to_insert:
        await db_session.execute(role_permissions.insert().values(links_to_insert))

    await db_session.commit()


@pytest_asyncio.fixture
async def auth_headers(admin_token: str) -> dict[str, str]:
    """Authorization headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
async def viewer_headers(viewer_token: str) -> dict[str, str]:
    """Authorization headers for viewer user (least-privileged)."""
    return {"Authorization": f"Bearer {viewer_token}"}


@pytest_asyncio.fixture
async def team_factory(db_session: AsyncSession):
    """Factory creating a team with an owner and (optionally) extra members."""

    async def _create(name: str, owner_user_id: int, member_ids: list[int] | None = None) -> Team:
        team = Team(name=name, owner_user_id=owner_user_id)
        db_session.add(team)
        await db_session.flush()
        db_session.add(TeamMember(team_id=team.id, user_id=owner_user_id, role=TeamRole.lead))
        for member_id in member_ids or []:
            db_session.add(TeamMember(team_id=team.id, user_id=member_id, role=TeamRole.member))
        await db_session.commit()
        await db_session.refresh(team)
        return team

    return _create


@pytest_asyncio.fixture
async def user_factory(db_session: AsyncSession):
    """Factory creating a bare active user (for multi-user visibility tests)."""

    async def _create(username: str) -> User:
        from app.core.security import get_password_hash

        user = User(
            username=username,
            email=f"{username}@test.com",
            hashed_password=get_password_hash("testpassword"),
            is_active=True,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _create
