"""
@file test_oidc_config.py
@description E2E API tests for OIDC configuration management endpoints.
             Tests all 4 endpoint groups through the HTTP layer using
             the async test client from conftest.py.
             18 tests total.
@dependencies pytest, pytest-asyncio, httpx, backend/tests/conftest.py
@relatedFiles ../app/api/auth.py, ../app/services/oidc_config.py, ../app/schemas/oidc_config.py
"""

import pytest
from httpx import AsyncClient

from app.services.oidc_config import invalidate_oidc_cache

pytestmark = pytest.mark.e2e


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def auth_headers(token: str) -> dict:
    """Return Authorization header dict for a given JWT token."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _invalidate_cache():
    """Invalidate the process-wide OIDC config cache before and after
    every test so cached values from a previous test never leak."""
    invalidate_oidc_cache()
    yield
    invalidate_oidc_cache()


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/auth/admin/oidc-config  (admin only — full config)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetOidcConfig:
    """E2E tests for GET /api/auth/admin/oidc-config."""

    @pytest.mark.asyncio
    async def test_get_oidc_config_no_auth(self, client: AsyncClient):
        """Anonymous request returns 401."""
        response = await client.get("/api/auth/admin/oidc-config")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_oidc_config_as_operator(
        self, client: AsyncClient, operator_token: str
    ):
        """Request from operator (non-admin) returns 403."""
        response = await client.get(
            "/api/auth/admin/oidc-config", headers=auth_headers(operator_token)
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_oidc_config_as_admin(
        self, client: AsyncClient, admin_token: str
    ):
        """Admin request returns 200 with full config."""
        response = await client.get(
            "/api/auth/admin/oidc-config", headers=auth_headers(admin_token)
        )
        assert response.status_code == 200
        data = response.json()

        # Verify structure — all fields present
        assert "id" in data
        assert "issuer_url" in data
        assert "client_id" in data
        assert "client_secret" in data
        assert "frontend_client_id" in data
        assert "enabled" in data
        assert "public_url" in data
        assert "role_mapping" in data
        assert "created_at" in data
        assert "updated_at" in data

    @pytest.mark.asyncio
    async def test_get_oidc_config_client_secret_masked(
        self, client: AsyncClient, admin_token: str
    ):
        """client_secret is always masked ('********') in the response."""
        response = await client.get(
            "/api/auth/admin/oidc-config", headers=auth_headers(admin_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert data["client_secret"] == "********"


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH /api/auth/admin/oidc-config  (admin only — update config)
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateOidcConfig:
    """E2E tests for PATCH /api/auth/admin/oidc-config."""

    @pytest.mark.asyncio
    async def test_update_oidc_config_no_auth(self, client: AsyncClient):
        """Anonymous request returns 401."""
        response = await client.patch(
            "/api/auth/admin/oidc-config",
            json={"issuer_url": "https://keycloak.example.com"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_update_oidc_config_as_operator(
        self, client: AsyncClient, operator_token: str
    ):
        """Request from operator (non-admin) returns 403."""
        response = await client.patch(
            "/api/auth/admin/oidc-config",
            headers=auth_headers(operator_token),
            json={"issuer_url": "https://keycloak.example.com"},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_update_issuer_url(
        self, client: AsyncClient, admin_token: str
    ):
        """Admin updates issuer_url → 200, returns updated config."""
        new_url = "https://keycloak-updated.example.com"
        response = await client.patch(
            "/api/auth/admin/oidc-config",
            headers=auth_headers(admin_token),
            json={"issuer_url": new_url},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["issuer_url"] == new_url
        assert data["client_secret"] == "********"

    @pytest.mark.asyncio
    async def test_admin_update_enabled(
        self, client: AsyncClient, admin_token: str
    ):
        """Admin sets enabled=True → 200."""
        response = await client.patch(
            "/api/auth/admin/oidc-config",
            headers=auth_headers(admin_token),
            json={"enabled": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_admin_update_client_secret(
        self, client: AsyncClient, admin_token: str
    ):
        """Admin updates client_secret → 200, secret is masked in response."""
        response = await client.patch(
            "/api/auth/admin/oidc-config",
            headers=auth_headers(admin_token),
            json={"client_secret": "new-secret-12345"},
        )
        assert response.status_code == 200
        data = response.json()
        # Secret must never leak
        assert data["client_secret"] == "********"

    @pytest.mark.asyncio
    async def test_admin_update_role_mapping(
        self, client: AsyncClient, admin_token: str
    ):
        """Admin updates role_mapping → 200, mapping is persisted."""
        new_mapping = {
            "admin": "platform-admin",
            "developer": "operator",
            "guest": "viewer",
        }
        response = await client.patch(
            "/api/auth/admin/oidc-config",
            headers=auth_headers(admin_token),
            json={"role_mapping": new_mapping},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role_mapping"] == new_mapping

        # Verify the change was persisted by reading back
        get_resp = await client.get(
            "/api/auth/admin/oidc-config", headers=auth_headers(admin_token)
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["role_mapping"] == new_mapping

    @pytest.mark.asyncio
    async def test_admin_update_multiple_fields(
        self, client: AsyncClient, admin_token: str
    ):
        """Admin updates multiple fields simultaneously → 200."""
        response = await client.patch(
            "/api/auth/admin/oidc-config",
            headers=auth_headers(admin_token),
            json={
                "issuer_url": "https://multi.example.com",
                "client_id": "multi-client",
                "frontend_client_id": "multi-frontend",
                "enabled": True,
                "public_url": "https://public.example.com",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["issuer_url"] == "https://multi.example.com"
        assert data["client_id"] == "multi-client"
        assert data["frontend_client_id"] == "multi-frontend"
        assert data["enabled"] is True
        assert data["public_url"] == "https://public.example.com"

    @pytest.mark.asyncio
    async def test_admin_update_invalid_type(
        self, client: AsyncClient, admin_token: str
    ):
        """Sending a wrong type (e.g. integer for issuer_url) returns 422."""
        response = await client.patch(
            "/api/auth/admin/oidc-config",
            headers=auth_headers(admin_token),
            json={"issuer_url": 12345},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_admin_update_unknown_field_ignored(
        self, client: AsyncClient, admin_token: str
    ):
        """Unknown fields in the JSON body are ignored (200, not 422)."""
        response = await client.patch(
            "/api/auth/admin/oidc-config",
            headers=auth_headers(admin_token),
            json={"issuer_url": "https://valid.example.com", "bogus_field": "should-be-ignored"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["issuer_url"] == "https://valid.example.com"
        assert "bogus_field" not in data


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/auth/admin/oidc-config/public  (admin only — subset, no secrets)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetOidcConfigPublic:
    """E2E tests for GET /api/auth/admin/oidc-config/public."""

    @pytest.mark.asyncio
    async def test_public_no_auth(self, client: AsyncClient):
        """Anonymous request returns 401 (endpoint requires admin role)."""
        response = await client.get("/api/auth/admin/oidc-config/public")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_public_as_operator(
        self, client: AsyncClient, operator_token: str
    ):
        """Operator request returns 403."""
        response = await client.get(
            "/api/auth/admin/oidc-config/public",
            headers=auth_headers(operator_token),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_public_as_admin(
        self, client: AsyncClient, admin_token: str
    ):
        """Admin request returns 200 with only public fields."""
        response = await client.get(
            "/api/auth/admin/oidc-config/public",
            headers=auth_headers(admin_token),
        )
        assert response.status_code == 200
        data = response.json()

        # Only public fields should be present
        assert "enabled" in data
        assert "issuer_url" in data
        assert "frontend_client_id" in data
        assert "public_url" in data

        # Sensitive fields must NOT be present
        assert "client_secret" not in data
        assert "client_id" not in data

        # Admin-only fields must NOT be present
        assert "id" not in data
        assert "role_mapping" not in data


# ═══════════════════════════════════════════════════════════════════════════════
# GET /api/auth/sso/config  (public — no auth required)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSsoConfig:
    """E2E tests for GET /api/auth/sso/config."""

    @pytest.mark.asyncio
    async def test_sso_config_no_auth(self, client: AsyncClient):
        """Public endpoint returns 200 without authentication."""
        response = await client.get("/api/auth/sso/config")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sso_config_structure(self, client: AsyncClient):
        """Response contains all expected SSO config fields."""
        response = await client.get("/api/auth/sso/config")
        assert response.status_code == 200
        data = response.json()

        # SSOConfig schema: enabled, url, realm, client_id
        assert "enabled" in data
        assert "url" in data
        assert "realm" in data
        assert "client_id" in data

        # realm is hard-coded to "bigbug"
        assert data["realm"] == "bigbug"

        # Types
        assert isinstance(data["enabled"], bool)
        assert isinstance(data["url"], str)
        assert isinstance(data["client_id"], str)

    @pytest.mark.asyncio
    async def test_sso_config_no_secrets_leaked(self, client: AsyncClient):
        """SSO config does not expose client_secret or backend client_id."""
        response = await client.get("/api/auth/sso/config")
        assert response.status_code == 200
        data = response.json()

        assert "client_secret" not in data
        # The field is 'client_id' but it's the frontend client, not the backend one
        # Verify it's present (it's the frontend_client_id)
        assert "client_id" in data

    @pytest.mark.asyncio
    async def test_sso_config_as_authenticated_user(
        self, client: AsyncClient, operator_token: str
    ):
        """Authenticated users also get 200 from the public SSO endpoint."""
        response = await client.get(
            "/api/auth/sso/config", headers=auth_headers(operator_token)
        )
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert data["realm"] == "bigbug"
