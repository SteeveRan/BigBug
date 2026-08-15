"""
@file test_pipeline_config_api.py
@description Integration tests for Pipeline Config API endpoints
             (git-mirroring v2) — list, create, get, update, delete, duplicate.
@dependencies pytest, pytest-asyncio, httpx, backend/tests/conftest.py
@relatedFiles ../../app/api/pipelines.py, ../../app/services/pipeline.py
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import RoleName
from app.models.gitlab_component import GitLabComponent
from app.models.permission import Permission, role_permissions
from app.models.role import Role

# Valid permissions required by integration endpoints
REQUIRED_PERMISSIONS = [
    {"name": "pipelines:read", "description": "Read pipeline runs"},
    {"name": "pipelines:write", "description": "Create and trigger pipelines"},
    {"name": "pipelines:delete", "description": "Cancel and delete pipelines"},
]


@pytest_asyncio.fixture(autouse=True)
async def seeded_permissions(db_session: AsyncSession):
    """Ensure the three standard roles exist and that the admin role
    has **every** permission listed in ``REQUIRED_PERMISSIONS``.
    """
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

    for perm_data in REQUIRED_PERMISSIONS:
        result = await db_session.execute(
            select(Permission).where(Permission.name == perm_data["name"])
        )
        perm = result.scalar_one_or_none()
        if perm is None:
            perm = Permission(name=perm_data["name"], description=perm_data["description"])
            db_session.add(perm)
            await db_session.flush()

        await db_session.refresh(admin_role, attribute_names=["permissions"])
        if perm not in admin_role.permissions:
            await db_session.execute(
                role_permissions.insert().values(role_id=admin_role.id, permission_id=perm.id)
            )

    await db_session.commit()


@pytest_asyncio.fixture(autouse=True)
async def seed_component(db_session: AsyncSession):
    """Ensure at least one GitLabComponent exists for pipeline component refs."""
    result = await db_session.execute(
        select(GitLabComponent).where(GitLabComponent.name == "integration-test-component")
    )
    if result.scalar_one_or_none() is not None:
        return
    comp = GitLabComponent(
        name="integration-test-component",
        provider_id=1,
        project_path="group/project",
        component_path=".gitlab/components/test.yml",
    )
    db_session.add(comp)
    await db_session.commit()


# ──────────────────────────────────────────────────────────────────────
# GET /configs
# ──────────────────────────────────────────────────────────────────────


class TestListConfigs:
    """Tests for GET /api/pipelines/configs"""

    @pytest.mark.asyncio
    async def test_list_configs_empty(self, client: AsyncClient, admin_token: str):
        """List returns empty array when no configs."""
        response = await client.get(
            "/api/pipelines/configs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_configs_with_items(self, client: AsyncClient, admin_token: str):
        """List returns created configs."""
        await client.post(
            "/api/pipelines/configs",
            json={"name": "list-a"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        await client.post(
            "/api/pipelines/configs",
            json={"name": "list-b"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await client.get(
            "/api/pipelines/configs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {item["name"] for item in data}
        assert names == {"list-a", "list-b"}


# ──────────────────────────────────────────────────────────────────────
# POST   /configs
# ──────────────────────────────────────────────────────────────────────


class TestCreateConfig:
    """Tests for POST /api/pipelines/configs"""

    @pytest.mark.asyncio
    async def test_create_config_minimal(self, client: AsyncClient, admin_token: str):
        """Create with name only."""
        response = await client.post(
            "/api/pipelines/configs",
            json={"name": "minimal-pipeline"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "minimal-pipeline"
        assert data["is_enabled"] is True
        assert data["is_default"] is False
        assert data["id"] is not None

    @pytest.mark.asyncio
    async def test_create_config_with_components(
        self, client: AsyncClient, admin_token: str, db_session: AsyncSession
    ):
        """Create with component references."""
        comp = (
            await db_session.execute(
                select(GitLabComponent).where(GitLabComponent.name == "integration-test-component")
            )
        ).scalar_one()

        response = await client.post(
            "/api/pipelines/configs",
            json={
                "name": "with-components",
                "description": "Has components",
                "ref": "main",
                "components": [{"component_id": comp.id, "order": 1, "overrides": {"env": "prod"}}],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "with-components"
        assert len(data["components"]) == 1
        assert data["components"][0]["component_id"] == comp.id
        assert data["components"][0]["overrides"] == {"env": "prod"}

    @pytest.mark.asyncio
    async def test_create_duplicate_name(self, client: AsyncClient, admin_token: str):
        """Duplicate name returns 409."""
        await client.post(
            "/api/pipelines/configs",
            json={"name": "dup-name"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        response = await client.post(
            "/api/pipelines/configs",
            json={"name": "dup-name"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
        assert "Name already in use" in response.json()["detail"]


# ──────────────────────────────────────────────────────────────────────
# GET    /configs/{id}
# ──────────────────────────────────────────────────────────────────────


class TestGetConfig:
    """Tests for GET /api/pipelines/configs/{id}"""

    @pytest.mark.asyncio
    async def test_get_config_found(self, client: AsyncClient, admin_token: str):
        """Get existing config."""
        create_resp = await client.post(
            "/api/pipelines/configs",
            json={"name": "get-me"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        config_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/pipelines/configs/{config_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "get-me"

    @pytest.mark.asyncio
    async def test_get_config_not_found(self, client: AsyncClient, admin_token: str):
        """Nonexistent config returns 404."""
        response = await client.get(
            "/api/pipelines/configs/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# PATCH  /configs/{id}
# ──────────────────────────────────────────────────────────────────────


class TestUpdateConfig:
    """Tests for PATCH /api/pipelines/configs/{id}"""

    @pytest.mark.asyncio
    async def test_update_config(self, client: AsyncClient, admin_token: str):
        """Update description and is_enabled."""
        create_resp = await client.post(
            "/api/pipelines/configs",
            json={"name": "update-me", "description": "old-desc"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        config_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/pipelines/configs/{config_id}",
            json={"description": "new-desc", "is_enabled": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "new-desc"
        assert data["is_enabled"] is False

    @pytest.mark.asyncio
    async def test_update_config_not_found(self, client: AsyncClient, admin_token: str):
        """PATCH on nonexistent config returns 404."""
        response = await client.patch(
            "/api/pipelines/configs/99999",
            json={"description": "nope"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# DELETE /configs/{id}
# ──────────────────────────────────────────────────────────────────────


class TestDeleteConfig:
    """Tests for DELETE /api/pipelines/configs/{id}"""

    @pytest.mark.asyncio
    async def test_delete_config(self, client: AsyncClient, admin_token: str):
        """Delete a non-default config."""
        create_resp = await client.post(
            "/api/pipelines/configs",
            json={"name": "delete-me"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        config_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/pipelines/configs/{config_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204
        assert response.content == b""

        # Verify it's gone
        get_resp = await client.get(
            f"/api/pipelines/configs/{config_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_default_fails(self, client: AsyncClient, admin_token: str):
        """Cannot delete default pipeline — returns 409."""
        create_resp = await client.post(
            "/api/pipelines/configs",
            json={"name": "default-deletable", "is_default": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        config_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/pipelines/configs/{config_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
        assert "Cannot delete default" in response.json()["detail"]


# ──────────────────────────────────────────────────────────────────────
# POST   /configs/{id}/duplicate
# ──────────────────────────────────────────────────────────────────────


class TestDuplicateConfig:
    """Tests for POST /api/pipelines/configs/{id}/duplicate"""

    @pytest.mark.asyncio
    async def test_duplicate_config(
        self, client: AsyncClient, admin_token: str, db_session: AsyncSession
    ):
        """Duplicate creates a copy with new name."""
        comp = (
            await db_session.execute(
                select(GitLabComponent).where(GitLabComponent.name == "integration-test-component")
            )
        ).scalar_one()

        create_resp = await client.post(
            "/api/pipelines/configs",
            json={
                "name": "original-pipe",
                "description": "Original",
                "is_enabled": False,
                "is_default": True,
                "components": [{"component_id": comp.id, "order": 1}],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        config_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/pipelines/configs/{config_id}/duplicate",
            json={"name": "duplicated-pipe"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "duplicated-pipe"
        assert data["description"] == "Original"
        assert data["is_enabled"] is False  # inherited
        assert data["is_default"] is False  # forced
        assert len(data["components"]) == 1

    @pytest.mark.asyncio
    async def test_duplicate_name_conflict(self, client: AsyncClient, admin_token: str):
        """Duplicate with existing name returns 409."""
        create_resp = await client.post(
            "/api/pipelines/configs",
            json={"name": "already-there"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        config_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/pipelines/configs/{config_id}/duplicate",
            json={"name": "already-there"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
