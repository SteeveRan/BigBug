"""
@file test_trust_store_api.py
@description API tests for /api/trust-stores (ADR-0037, issue #89): RBAC
              (operator read ok / write 403, admin ok), certificate chain
              upload, single certificate delete, usage, and
              trust_store_id on POST/PATCH /api/providers + ProviderOut.
@dependencies backend/app/api/trust_stores.py, backend/tests/conftest.py
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import RoleName
from app.models.permission import Permission, role_permissions
from app.models.role import Role
from tests.unit._trust_certs_fixtures import PEM_CA1, PEM_CA2

REQUIRED_PERMISSIONS = [
    {"name": "trust_stores:read", "description": "View trust stores"},
    {"name": "trust_stores:write", "description": "Manage trust stores"},
    {"name": "providers:write", "description": "Create providers"},
    {"name": "providers:read", "description": "Read providers"},
]


@pytest_asyncio.fixture(autouse=True)
async def seeded_permissions(db_session: AsyncSession):
    """Seed the roles and grant all REQUIRED_PERMISSIONS to admin only."""
    for name in [RoleName.ADMIN.value, RoleName.OPERATOR.value, RoleName.VIEWER.value]:
        result = await db_session.execute(select(Role).where(Role.name == name))
        if result.scalar_one_or_none() is None:
            db_session.add(Role(name=name, description=f"{name.capitalize()} role"))
    await db_session.flush()

    admin_role = (
        await db_session.execute(select(Role).where(Role.name == RoleName.ADMIN.value))
    ).scalar_one()

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


@pytest_asyncio.fixture
async def store_id(client: AsyncClient, admin_token: str) -> int:
    response = await client.post(
        "/api/trust-stores",
        json={"name": "corp-ca"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


# ──────────────────────────────────────────────────────────────────────
# RBAC
# ──────────────────────────────────────────────────────────────────────


class TestRBAC:
    @pytest.mark.asyncio
    async def test_admin_read_ok(self, client: AsyncClient, admin_token: str, store_id: int):
        response = await client.get(
            "/api/trust-stores", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert [s["name"] for s in response.json()] == ["corp-ca"]

    @pytest.mark.asyncio
    async def test_anonymous_401(self, client: AsyncClient):
        response = await client.get("/api/trust-stores")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_operator_write_403(self, client: AsyncClient, operator_token: str):
        response = await client.post(
            "/api/trust-stores",
            json={"name": "op-store"},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_operator_read_ok(
        self,
        db_session: AsyncSession,
        client: AsyncClient,
        operator_token: str,
        admin_token: str,
        store_id: int,
    ):
        """Operator holds trust_stores:read (needed to bind a store to a provider)."""
        role = (
            await db_session.execute(select(Role).where(Role.name == RoleName.OPERATOR.value))
        ).scalar_one()
        perm = (
            await db_session.execute(
                select(Permission).where(Permission.name == "trust_stores:read")
            )
        ).scalar_one()
        await db_session.execute(
            role_permissions.insert().values(role_id=role.id, permission_id=perm.id)
        )
        await db_session.commit()

        response = await client.get(
            "/api/trust-stores", headers={"Authorization": f"Bearer {operator_token}"}
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_operator_delete_403(
        self, client: AsyncClient, operator_token: str, store_id: int
    ):
        response = await client.delete(
            f"/api/trust-stores/{store_id}",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 403


# ──────────────────────────────────────────────────────────────────────
# Certificates
# ──────────────────────────────────────────────────────────────────────


class TestCertificatesAPI:
    @pytest.mark.asyncio
    async def test_add_single_certificate(
        self, client: AsyncClient, admin_token: str, store_id: int
    ):
        response = await client.post(
            f"/api/trust-stores/{store_id}/certificates",
            json={"name": "root", "pem": PEM_CA1},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "root"
        assert len(data[0]["fingerprint"]) == 64

    @pytest.mark.asyncio
    async def test_add_chain_of_three_creates_three_rows(
        self, client: AsyncClient, admin_token: str, store_id: int
    ):
        chain = "\n".join([PEM_CA1, PEM_CA2, PEM_CA1])
        response = await client.post(
            f"/api/trust-stores/{store_id}/certificates",
            json={"name": "chain", "pem": chain},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data) == 3
        assert {c["name"] for c in data} == {"chain-1", "chain-2", "chain-3"}

    @pytest.mark.asyncio
    async def test_add_certificates_list_form(
        self, client: AsyncClient, admin_token: str, store_id: int
    ):
        response = await client.post(
            f"/api/trust-stores/{store_id}/certificates",
            json={"certificates": [{"name": "a", "pem": PEM_CA1}, {"name": "b", "pem": PEM_CA2}]},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201
        assert {c["name"] for c in response.json()} == {"a", "b"}

    @pytest.mark.asyncio
    async def test_delete_single_certificate(
        self, client: AsyncClient, admin_token: str, store_id: int
    ):
        created = (
            await client.post(
                f"/api/trust-stores/{store_id}/certificates",
                json={
                    "certificates": [
                        {"name": "a", "pem": PEM_CA1},
                        {"name": "b", "pem": PEM_CA2},
                    ]
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        ).json()
        target_id = created[0]["id"]

        response = await client.delete(
            f"/api/trust-stores/{store_id}/certificates/{target_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 204

        store = (
            await client.get(
                f"/api/trust-stores/{store_id}", headers={"Authorization": f"Bearer {admin_token}"}
            )
        ).json()
        assert [c["id"] for c in store["certificates"]] != [target_id]
        assert len(store["certificates"]) == 1

    @pytest.mark.asyncio
    async def test_invalid_pem_422(self, client: AsyncClient, admin_token: str, store_id: int):
        response = await client.post(
            f"/api/trust-stores/{store_id}/certificates",
            json={"name": "bad", "pem": "garbage"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_operator_cannot_add_certificate(
        self, client: AsyncClient, operator_token: str, store_id: int
    ):
        response = await client.post(
            f"/api/trust-stores/{store_id}/certificates",
            json={"name": "x", "pem": PEM_CA1},
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert response.status_code == 403


# ──────────────────────────────────────────────────────────────────────
# Usage gate
# ──────────────────────────────────────────────────────────────────────


class TestDeleteUsage:
    @pytest.mark.asyncio
    async def test_delete_store_in_use_409(
        self, client: AsyncClient, admin_token: str, db_session: AsyncSession, store_id: int
    ):
        from app.models.resource_provider import (
            ProviderCategory,
            ProviderDirection,
            ProviderDomain,
            ProviderSubtype,
            ResourceProvider,
        )

        db_session.add(
            ResourceProvider(
                domain=ProviderDomain.git,
                subtype=ProviderSubtype.gitlab,
                category=ProviderCategory.public,
                direction=ProviderDirection.external,
                name="gitlab-prod",
                label="GitLab Prod",
                trust_store_id=store_id,
            )
        )
        await db_session.commit()

        usage = await client.get(
            f"/api/trust-stores/{store_id}/usage",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert usage.status_code == 200
        assert usage.json()["providers"] == ["gitlab-prod"]

        response = await client.delete(
            f"/api/trust-stores/{store_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 409
        assert "gitlab-prod" in response.json()["detail"]


# ──────────────────────────────────────────────────────────────────────
# Provider ↔ trust_store wiring
# ──────────────────────────────────────────────────────────────────────


class TestProviderTrustStoreLink:
    @pytest.mark.asyncio
    async def test_provider_create_with_trust_store_id_roundtrip(
        self, client: AsyncClient, admin_token: str, store_id: int
    ):
        response = await client.post(
            "/api/providers",
            json={
                "domain": "git",
                "subtype": "gitlab",
                "category": "public",
                "direction": "external",
                "name": "gl",
                "label": "GL",
                "base_url": "https://gitlab.example.com",
                "trust_store_id": store_id,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["trust_store_id"] == store_id

        provider_id = response.json()["id"]
        fetched = (
            await client.get(
                f"/api/providers/{provider_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        ).json()
        assert fetched["trust_store_id"] == store_id

    @pytest.mark.asyncio
    async def test_provider_patch_trust_store_id(
        self, client: AsyncClient, admin_token: str, store_id: int
    ):
        created = (
            await client.post(
                "/api/providers",
                json={
                    "domain": "git",
                    "subtype": "gitlab",
                    "category": "public",
                    "direction": "external",
                    "name": "gl2",
                    "label": "GL2",
                    "base_url": "https://gitlab.example.com",
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        ).json()

        patched = (
            await client.patch(
                f"/api/providers/{created['id']}",
                json={"trust_store_id": store_id},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        ).json()
        assert patched["trust_store_id"] == store_id

    @pytest.mark.asyncio
    async def test_provider_patch_trust_store_null_unbinds(
        self, client: AsyncClient, admin_token: str, store_id: int
    ):
        """Explicit null in PATCH unbinds the store (clearing the form Select)."""
        created = (
            await client.post(
                "/api/providers",
                json={
                    "domain": "git",
                    "subtype": "gitlab",
                    "category": "public",
                    "direction": "external",
                    "name": "gl3",
                    "label": "GL3",
                    "base_url": "https://gitlab.example.com",
                    "trust_store_id": store_id,
                },
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        ).json()
        assert created["trust_store_id"] == store_id

        patched = (
            await client.patch(
                f"/api/providers/{created['id']}",
                json={"trust_store_id": None},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
        ).json()
        assert patched["trust_store_id"] is None
