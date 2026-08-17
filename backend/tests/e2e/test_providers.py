"""
@file test_providers.py
@description E2E tests for the unified Providers V3 API against a live backend:
              types metadata, CRUD, 409 duplicate, 422 validation, system-create
              403, owner=me filtering, RBAC (viewer 403 on write, operator
              denied is_default), and per-response OpenAPI contract validation.
@dependencies backend/tests/e2e/conftest.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def private_payload(name: str) -> dict:
    return {
        "domain": "git",
        "subtype": "github",
        "category": "private",
        "direction": "external",
        "name": name,
        "label": name,
    }


def public_payload(name: str) -> dict:
    return {
        "domain": "git",
        "subtype": "github",
        "category": "public",
        "direction": "external",
        "name": name,
        "label": name,
    }


async def _delete_provider(client: AsyncClient, headers: dict, provider_id: int) -> None:
    """Best-effort cleanup of a created provider (soft delete)."""
    await client.delete(f"/api/providers/{provider_id}", headers=headers)


class TestProviderTypes:
    async def test_get_types_200(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/providers/types", headers=admin_headers)
        assert_matches_openapi(response, "/api/providers/types", "get", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data, "registry must expose at least one subtype"
        required = {"subtype", "domain", "label", "capabilities", "config_schema"}
        assert required <= set(data[0])


class TestProviderCrud:
    async def test_create_get_update_delete(
        self,
        client: AsyncClient,
        admin_headers: dict,
        unique_name: str,
        openapi_spec: dict,
    ):
        name = f"crud-{unique_name}"
        create = await client.post(
            "/api/providers", headers=admin_headers, json=private_payload(name)
        )
        assert_matches_openapi(create, "/api/providers", "post", openapi_spec)
        assert create.status_code == 201
        created = create.json()
        assert created["name"] == name
        assert created["owner_user_id"] is not None

        get = await client.get(f"/api/providers/{created['id']}", headers=admin_headers)
        assert_matches_openapi(get, "/api/providers/{provider_id}", "get", openapi_spec)
        assert get.status_code == 200
        assert get.json()["name"] == name

        patch = await client.patch(
            f"/api/providers/{created['id']}",
            headers=admin_headers,
            json={"label": f"{name}-renamed"},
        )
        assert_matches_openapi(patch, "/api/providers/{provider_id}", "patch", openapi_spec)
        assert patch.status_code == 200
        assert patch.json()["label"] == f"{name}-renamed"

        delete = await client.delete(f"/api/providers/{created['id']}", headers=admin_headers)
        assert_matches_openapi(delete, "/api/providers/{provider_id}", "delete", openapi_spec)
        assert delete.status_code == 204

    async def test_create_duplicate_name_409(
        self, client: AsyncClient, admin_headers: dict, unique_name: str
    ):
        name = f"dup-{unique_name}"
        first = await client.post(
            "/api/providers", headers=admin_headers, json=private_payload(name)
        )
        assert first.status_code == 201
        try:
            second = await client.post(
                "/api/providers", headers=admin_headers, json=private_payload(name)
            )
            assert second.status_code == 409
        finally:
            await _delete_provider(client, admin_headers, first.json()["id"])

    async def test_create_invalid_category_422(
        self, client: AsyncClient, admin_headers: dict, unique_name: str
    ):
        payload = private_payload(f"invalid-{unique_name}")
        payload["category"] = "system"  # github does not allow system
        response = await client.post("/api/providers", headers=admin_headers, json=payload)
        assert response.status_code == 422

    async def test_create_system_provider_forbidden(
        self, client: AsyncClient, admin_headers: dict, unique_name: str
    ):
        payload = {
            "domain": "git",
            "subtype": "gitlab",
            "category": "system",
            "direction": "internal",
            "name": f"system-{unique_name}",
            "label": f"system-{unique_name}",
            "base_url": "https://gitlab.internal.example.com",
        }
        response = await client.post("/api/providers", headers=admin_headers, json=payload)
        assert response.status_code == 403
        assert "cannot be created via the API" in response.json()["detail"]


class TestProviderVisibility:
    async def test_owner_me_filter(
        self,
        client: AsyncClient,
        admin_headers: dict,
        unique_name: str,
        openapi_spec: dict,
    ):
        private_name = f"mine-{unique_name}"
        public_name = f"shared-{unique_name}"
        private = await client.post(
            "/api/providers", headers=admin_headers, json=private_payload(private_name)
        )
        assert private.status_code == 201
        public = await client.post(
            "/api/providers", headers=admin_headers, json=public_payload(public_name)
        )
        assert public.status_code == 201
        try:
            response = await client.get(
                "/api/providers", headers=admin_headers, params={"owner": "me"}
            )
            assert_matches_openapi(response, "/api/providers", "get", openapi_spec)
            assert response.status_code == 200
            names = {p["name"] for p in response.json()}
            assert private_name in names
            assert public_name not in names
        finally:
            await _delete_provider(client, admin_headers, private.json()["id"])
            await _delete_provider(client, admin_headers, public.json()["id"])

    async def test_viewer_without_write_403(
        self, client: AsyncClient, viewer_headers: dict, unique_name: str
    ):
        response = await client.post(
            "/api/providers",
            headers=viewer_headers,
            json=private_payload(f"viewer-{unique_name}"),
        )
        assert response.status_code == 403

    async def test_operator_cannot_set_default(
        self,
        client: AsyncClient,
        admin_headers: dict,
        operator_headers: dict,
        unique_name: str,
    ):
        # The mutation that would flip is_default is rejected up-front (403), so
        # seeded default providers are never modified.
        create = await client.post(
            "/api/providers",
            headers=admin_headers,
            json=public_payload(f"default-{unique_name}"),
        )
        assert create.status_code == 201
        try:
            operator_patch = await client.patch(
                f"/api/providers/{create.json()['id']}",
                headers=operator_headers,
                json={"is_default": True},
            )
            assert operator_patch.status_code == 403
        finally:
            await _delete_provider(client, admin_headers, create.json()["id"])

    async def test_viewer_can_read_200(
        self, client: AsyncClient, viewer_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/providers", headers=viewer_headers)
        assert_matches_openapi(response, "/api/providers", "get", openapi_spec)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestProviderActions:
    async def test_provider_test_connection_200(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        providers = await client.get("/api/providers", headers=admin_headers)
        assert providers.status_code == 200
        data = providers.json()
        assert data, "at least one seeded provider is expected"
        provider_id = data[0]["id"]

        response = await client.post(f"/api/providers/{provider_id}/test", headers=admin_headers)
        assert_matches_openapi(response, "/api/providers/{provider_id}/test", "post", openapi_spec)
        assert response.status_code == 200

    async def test_provider_invalid_action_422(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        providers = await client.get("/api/providers", headers=admin_headers)
        provider_id = providers.json()[0]["id"]

        response = await client.post(
            f"/api/providers/{provider_id}/actions/bogus", headers=admin_headers
        )
        assert_matches_openapi(
            response, "/api/providers/{provider_id}/actions/{action}", "post", openapi_spec
        )
        assert response.status_code == 422
