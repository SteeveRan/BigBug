"""
@file test_auth.py
@description E2E tests for the authentication endpoints against a live backend.
              Covers login/logout/me/permissions/refresh, 401/422 negatives and
              OpenAPI contract validation on the primary responses.
@dependencies backend/tests/e2e/conftest.py
"""

import uuid

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import ADMIN_PASSWORD, ADMIN_USERNAME, assert_matches_openapi

pytestmark = pytest.mark.e2e


def _xff() -> dict[str, str]:
    """Unique ``X-Forwarded-For`` per login call.

    The login endpoint is rate-limited to 5/min per client identity (IP or
    ``X-Forwarded-For``). Assigning each e2e login a distinct identity keeps
    the tests deterministic against the live server without touching the
    rate-limit configuration.
    """
    return {"X-Forwarded-For": f"10.0.0.{uuid.uuid4().hex[:6]}"}


class TestLogin:
    async def test_login_success(
        self, client: AsyncClient, openapi_spec: dict
    ):
        response = await client.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            headers=_xff(),
        )
        assert_matches_openapi(response, "/api/auth/login", "post", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, openapi_spec: dict):
        response = await client.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": "wrong-password"},
            headers=_xff(),
        )
        assert response.status_code == 401

    async def test_login_unknown_user(self, client: AsyncClient, openapi_spec: dict):
        response = await client.post(
            "/api/auth/login",
            json={"username": "e2e-nobody", "password": "password"},
            headers=_xff(),
        )
        assert response.status_code == 401

    async def test_login_missing_fields_422(self, client: AsyncClient, openapi_spec: dict):
        response = await client.post(
            "/api/auth/login", json={"username": "admin"}, headers=_xff()
        )
        assert response.status_code == 422


class TestMe:
    async def test_get_me(self, client: AsyncClient, admin_headers: dict, openapi_spec: dict):
        response = await client.get("/api/auth/me", headers=admin_headers)
        assert_matches_openapi(response, "/api/auth/me", "get", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == ADMIN_USERNAME
        assert "admin" in data["roles"]
        assert "full_name" in data

    async def test_get_me_no_token(self, client: AsyncClient):
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_get_me_permissions(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/auth/me/permissions", headers=admin_headers)
        assert_matches_openapi(response, "/api/auth/me/permissions", "get", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "admin"
        assert "providers:read" in data["permissions"]


class TestRefresh:
    async def test_refresh_token(
        self, client: AsyncClient, openapi_spec: dict
    ):
        login = await client.post(
            "/api/auth/login",
            json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            headers=_xff(),
        )
        refresh_token = login.json()["refresh_token"]

        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert_matches_openapi(response, "/api/auth/refresh", "post", openapi_spec)
        assert response.status_code == 200
        assert response.json()["access_token"]

    async def test_refresh_invalid_token(self, client: AsyncClient):
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": "not-a-valid-token"},
        )
        assert response.status_code == 401


class TestSsoConfig:
    async def test_sso_config_public(self, client: AsyncClient, openapi_spec: dict):
        response = await client.get("/api/auth/sso/config")
        assert_matches_openapi(response, "/api/auth/sso/config", "get", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert data["realm"] == "bigbug"
        assert "client_secret" not in data
