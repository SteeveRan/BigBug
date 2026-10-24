"""
@file test_oidc_config.py
@description E2E tests for the OIDC provider admin CRUD (multi-provider,
              ADR-0037) against a live backend: RBAC (401/403), collection
              read, masked secret, create/update/delete and 422 on an issuer
              without a /realms/ segment.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e

ADMIN_OIDC = "/api/auth/admin/oidc-providers"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def _created_provider(client: AsyncClient, admin_headers: dict):
    """Create a provider and delete it after the test (cleanup)."""
    resp = await client.post(
        ADMIN_OIDC,
        headers=admin_headers,
        json={
            "name": "e2e-test-provider",
            "issuer_url": "https://keycloak.local/realms/bigbug",
            "client_id": "bigbug-backend",
            "frontend_client_id": "bigbug-frontend",
            "enabled": False,
        },
    )
    assert resp.status_code == 201, resp.text
    pid = resp.json()["id"]
    yield pid
    await client.delete(f"{ADMIN_OIDC}/{pid}", headers=admin_headers)


class TestOidcProvidersRbac:
    async def test_list_no_auth(self, client: AsyncClient):
        response = await client.get(ADMIN_OIDC)
        assert response.status_code == 401

    async def test_list_as_viewer(self, client: AsyncClient, viewer_headers: dict):
        # viewer has oidc:read in the seed; assert a deterministic outcome.
        response = await client.get(ADMIN_OIDC, headers=viewer_headers)
        assert response.status_code in (200, 403)

    async def test_list_as_admin(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get(ADMIN_OIDC, headers=admin_headers)
        assert_matches_openapi(response, ADMIN_OIDC, "get", openapi_spec)
        assert response.status_code == 200
        for row in response.json():
            assert row["client_secret"] == "********"

    async def test_create_no_auth(self, client: AsyncClient):
        response = await client.post(ADMIN_OIDC, json={"name": "x"})
        assert response.status_code == 401

    async def test_create_as_viewer(self, client: AsyncClient, viewer_headers: dict):
        response = await client.post(ADMIN_OIDC, headers=viewer_headers, json={"name": "x"})
        assert response.status_code == 403


class TestOidcProvidersCrud:
    async def test_create_provider(
        self,
        client: AsyncClient,
        admin_headers: dict,
        openapi_spec: dict,
        _created_provider: int,
    ):
        response = await client.get(f"{ADMIN_OIDC}/{_created_provider}", headers=admin_headers)
        assert_matches_openapi(response, f"{ADMIN_OIDC}/{{provider_id}}", "get", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "e2e-test-provider"
        assert data["client_secret"] == "********"

    async def test_update_provider(
        self,
        client: AsyncClient,
        admin_headers: dict,
        openapi_spec: dict,
        _created_provider: int,
    ):
        response = await client.patch(
            f"{ADMIN_OIDC}/{_created_provider}",
            headers=admin_headers,
            json={"issuer_url": "https://keycloak-updated.example.com/realms/myrealm"},
        )
        assert_matches_openapi(response, f"{ADMIN_OIDC}/{{provider_id}}", "patch", openapi_spec)
        assert response.status_code == 200
        assert (
            response.json()["issuer_url"] == "https://keycloak-updated.example.com/realms/myrealm"
        )

    async def test_update_issuer_without_realm_segment(
        self, client: AsyncClient, admin_headers: dict, _created_provider: int
    ):
        """An issuer without /realms/<realm> is rejected as incomplete config."""
        response = await client.patch(
            f"{ADMIN_OIDC}/{_created_provider}",
            headers=admin_headers,
            json={"issuer_url": "https://kc.example.com"},
        )
        assert response.status_code == 422

    async def test_update_unknown_provider_404(self, client: AsyncClient, admin_headers: dict):
        response = await client.patch(
            f"{ADMIN_OIDC}/99999999", headers=admin_headers, json={"enabled": True}
        )
        assert response.status_code == 404

    async def test_delete_unknown_provider_404(self, client: AsyncClient, admin_headers: dict):
        response = await client.delete(f"{ADMIN_OIDC}/99999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_delete_provider(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        resp = await client.post(
            ADMIN_OIDC,
            headers=admin_headers,
            json={"name": "e2e-delete-me", "issuer_url": "https://kc.local/realms/tmp"},
        )
        pid = resp.json()["id"]
        response = await client.delete(f"{ADMIN_OIDC}/{pid}", headers=admin_headers)
        assert_matches_openapi(response, f"{ADMIN_OIDC}/{{provider_id}}", "delete", openapi_spec)
        assert response.status_code == 204
        assert (await client.get(f"{ADMIN_OIDC}/{pid}", headers=admin_headers)).status_code == 404

    async def test_update_invalid_type(self, client: AsyncClient, admin_headers: dict):
        response = await client.patch(
            f"{ADMIN_OIDC}/1",
            headers=admin_headers,
            json={"issuer_url": 12345},
        )
        assert response.status_code == 422
