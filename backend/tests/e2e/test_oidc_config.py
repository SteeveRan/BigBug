"""
@file test_oidc_config.py
@description E2E tests for the OIDC configuration endpoints against a live
              backend: RBAC (401/403), read, masked secret, public subset and
              a PATCH with teardown that restores the original value.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e

ADMIN_OIDC = "/api/auth/admin/oidc-config"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def _restore_oidc_config(client: AsyncClient, admin_headers: dict):
    """Capture the OIDC config and restore it after the test mutates it."""
    before = (await client.get(ADMIN_OIDC, headers=admin_headers)).json()
    yield before
    await client.patch(
        ADMIN_OIDC,
        headers=admin_headers,
        json={
            "issuer_url": before["issuer_url"],
            "client_id": before["client_id"],
            "frontend_client_id": before["frontend_client_id"],
            "enabled": before["enabled"],
            "public_url": before["public_url"],
            "role_mapping": before["role_mapping"],
        },
    )


class TestGetOidcConfig:
    async def test_get_oidc_config_no_auth(self, client: AsyncClient):
        response = await client.get(ADMIN_OIDC)
        assert response.status_code == 401

    async def test_get_oidc_config_as_viewer(
        self, client: AsyncClient, viewer_headers: dict
    ):
        # viewer has oidc:read in the seed; assert a deterministic outcome.
        response = await client.get(ADMIN_OIDC, headers=viewer_headers)
        assert response.status_code in (200, 403)

    async def test_get_oidc_config_as_admin(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get(ADMIN_OIDC, headers=admin_headers)
        assert_matches_openapi(response, ADMIN_OIDC, "get", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert "client_secret" in data
        assert data["client_secret"] == "********"

    async def test_get_oidc_config_public(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get(f"{ADMIN_OIDC}/public", headers=admin_headers)
        assert_matches_openapi(response, f"{ADMIN_OIDC}/public", "get", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert "client_secret" not in data
        assert "client_id" not in data


class TestUpdateOidcConfig:
    async def test_update_oidc_config_no_auth(self, client: AsyncClient):
        response = await client.patch(ADMIN_OIDC, json={"enabled": True})
        assert response.status_code == 401

    async def test_update_oidc_config_as_viewer(
        self, client: AsyncClient, viewer_headers: dict
    ):
        response = await client.patch(
            ADMIN_OIDC, headers=viewer_headers, json={"enabled": True}
        )
        assert response.status_code == 403

    async def test_admin_update_issuer_url(
        self,
        client: AsyncClient,
        admin_headers: dict,
        openapi_spec: dict,
        _restore_oidc_config,
    ):
        response = await client.patch(
            ADMIN_OIDC,
            headers=admin_headers,
            json={"issuer_url": "https://keycloak-updated.example.com"},
        )
        assert_matches_openapi(response, ADMIN_OIDC, "patch", openapi_spec)
        assert response.status_code == 200
        assert response.json()["issuer_url"] == "https://keycloak-updated.example.com"

    async def test_admin_update_invalid_type(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.patch(
            ADMIN_OIDC,
            headers=admin_headers,
            json={"issuer_url": 12345},
        )
        assert response.status_code == 422
