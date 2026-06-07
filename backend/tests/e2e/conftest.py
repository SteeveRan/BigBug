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

# Valid Fernet key for tests (same as unit/conftest.py)
_VALID_FERNET_KEY = "Z0lZSjZpc3gyMDI1Y29vbHByb2plY3RmZXJuZXRrZXk="

# Permissions required by integration endpoints
REQUIRED_PERMISSIONS = [
    {"name": "integrations:manage", "description": "Manage GitLab, Harbor, GitHub instances"},
    {"name": "docker_registry:manage", "description": "Manage Docker Registry instances"},
    {"name": "helm_repository:manage", "description": "Manage Helm Repository instances"},
    {"name": "pipelines:read", "description": "Read pipeline runs"},
    {"name": "pipelines:manage", "description": "Trigger and manage pipeline runs"},
    {"name": "users:read", "description": "Read users and audit logs"},
]


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
    """Ensure the three standard roles exist and that the admin role
    has **every** permission listed in ``REQUIRED_PERMISSIONS``.

    *Autouse* so permissions are present regardless of which fixtures a
    particular test happens to request — this is critical when tests that
    don't need ``admin_token`` run before tests that do, because the
    root conftest creates the roles *without* the extra e2e permissions.
    """
    # ── ensure the three standard roles exist ──────────────────────────
    role_names = [RoleName.ADMIN.value, RoleName.OPERATOR.value, RoleName.VIEWER.value]
    roles: dict[str, Role] = {}
    for name in role_names:
        result = await db_session.execute(select(Role).where(Role.name == name))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=name, description=f"{name.capitalize()} role")
            db_session.add(role)
            await db_session.flush()
        roles[name] = role
    admin_role = roles[RoleName.ADMIN.value]

    # ── ensure required permissions exist and are assigned to admin ────
    for perm_data in REQUIRED_PERMISSIONS:
        result = await db_session.execute(
            select(Permission).where(Permission.name == perm_data["name"])
        )
        perm = result.scalar_one_or_none()
        if perm is None:
            perm = Permission(name=perm_data["name"], description=perm_data["description"])
            db_session.add(perm)
            await db_session.flush()

        # Refresh admin_role.permissions relationship for idempotency check
        await db_session.refresh(admin_role, attribute_names=["permissions"])
        if perm not in admin_role.permissions:
            await db_session.execute(
                role_permissions.insert().values(role_id=admin_role.id, permission_id=perm.id)
            )

    await db_session.commit()


@pytest_asyncio.fixture
async def auth_headers(admin_token: str) -> dict[str, str]:
    """Authorization headers for admin user."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest_asyncio.fixture
async def viewer_headers(viewer_token: str) -> dict[str, str]:
    """Authorization headers for viewer user (least-privileged)."""
    return {"Authorization": f"Bearer {viewer_token}"}
