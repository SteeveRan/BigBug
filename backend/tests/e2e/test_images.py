"""
@file test_images.py
@description E2E tests for Gold/App image CRUD (/api/gold-images,
              /api/app-images) against a live backend. CRUD is pure DB I/O
              (no external calls), with data isolation via unique names and
              teardown DELETE. No sqlite fixtures, no mocks.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestGoldImages:
    async def test_list_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/gold-images")
        assert response.status_code == 401

    async def test_crud(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        name = f"gold-{unique_name}"
        create = await client.post(
            "/api/gold-images",
            headers=admin_headers,
            json={
                "name": name,
                "os_family": "alpine",
                "description": "e2e gold image",
                "dockerfile": "FROM alpine:3.19",
            },
        )
        assert_matches_openapi(create, "/api/gold-images", "post", openapi_spec)
        assert create.status_code == 201
        created = create.json()
        assert created["name"] == name
        assert created["os_family"] == "alpine"

        get = await client.get(f"/api/gold-images/{created['id']}", headers=admin_headers)
        assert_matches_openapi(get, "/api/gold-images/{image_id}", "get", openapi_spec)
        assert get.status_code == 200
        assert get.json()["name"] == name

        patch = await client.patch(
            f"/api/gold-images/{created['id']}",
            headers=admin_headers,
            json={"description": "updated"},
        )
        assert_matches_openapi(patch, "/api/gold-images/{image_id}", "patch", openapi_spec)
        assert patch.status_code == 200
        assert patch.json()["description"] == "updated"

        delete = await client.delete(f"/api/gold-images/{created['id']}", headers=admin_headers)
        assert_matches_openapi(delete, "/api/gold-images/{image_id}", "delete", openapi_spec)
        assert delete.status_code == 204

    async def test_list_200(self, client: AsyncClient, admin_headers: dict, openapi_spec: dict):
        response = await client.get("/api/gold-images", headers=admin_headers)
        assert_matches_openapi(response, "/api/gold-images", "get", openapi_spec)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.get("/api/gold-images/999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.delete("/api/gold-images/999999", headers=admin_headers)
        assert response.status_code == 404


class TestAppImages:
    async def test_crud(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        name = f"app-{unique_name}"
        create = await client.post(
            "/api/app-images",
            headers=admin_headers,
            json={
                "name": name,
                "description": "e2e app image",
                "dockerfile": "FROM scratch",
            },
        )
        assert_matches_openapi(create, "/api/app-images", "post", openapi_spec)
        assert create.status_code == 201
        created = create.json()
        assert created["name"] == name

        get = await client.get(f"/api/app-images/{created['id']}", headers=admin_headers)
        assert_matches_openapi(get, "/api/app-images/{image_id}", "get", openapi_spec)
        assert get.status_code == 200

        delete = await client.delete(f"/api/app-images/{created['id']}", headers=admin_headers)
        assert_matches_openapi(delete, "/api/app-images/{image_id}", "delete", openapi_spec)
        assert delete.status_code == 204

    async def test_list_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/app-images")
        assert response.status_code == 401

    async def test_get_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.get("/api/app-images/999999", headers=admin_headers)
        assert response.status_code == 404


class TestGoldImageValidation:
    """Documented 422 validation paths (invalid integer path params)."""

    @pytest.mark.parametrize(
        ("method", "url", "template"),
        [
            ("post", "/api/gold-images/abc/build", "/api/gold-images/{image_id}/build"),
            (
                "post",
                "/api/gold-images/abc/versions/999/scan",
                "/api/gold-images/{image_id}/versions/{version_id}/scan",
            ),
            (
                "post",
                "/api/gold-images/abc/versions/999/scan/results",
                "/api/gold-images/{image_id}/versions/{version_id}/scan/results",
            ),
            (
                "post",
                "/api/gold-images/abc/versions/999/sign",
                "/api/gold-images/{image_id}/versions/{version_id}/sign",
            ),
            (
                "post",
                "/api/gold-images/abc/versions/999/verify",
                "/api/gold-images/{image_id}/versions/{version_id}/verify",
            ),
        ],
    )
    async def test_invalid_path_param_422(
        self,
        client: AsyncClient,
        admin_headers: dict,
        openapi_spec: dict,
        method: str,
        url: str,
        template: str,
    ):
        response = await client.post(url, headers=admin_headers, json={})
        assert_matches_openapi(response, template, method, openapi_spec)
        assert response.status_code == 422


class TestAppImageValidation:
    """Documented 422 validation paths (invalid integer path params)."""

    @pytest.mark.parametrize(
        ("method", "url", "template"),
        [
            ("patch", "/api/app-images/abc", "/api/app-images/{image_id}"),
            ("post", "/api/app-images/abc/build", "/api/app-images/{image_id}/build"),
            (
                "post",
                "/api/app-images/abc/versions/999/scan",
                "/api/app-images/{image_id}/versions/{version_id}/scan",
            ),
            (
                "post",
                "/api/app-images/abc/versions/999/scan/results",
                "/api/app-images/{image_id}/versions/{version_id}/scan/results",
            ),
            (
                "post",
                "/api/app-images/abc/versions/999/sign",
                "/api/app-images/{image_id}/versions/{version_id}/sign",
            ),
            (
                "post",
                "/api/app-images/abc/versions/999/verify",
                "/api/app-images/{image_id}/versions/{version_id}/verify",
            ),
        ],
    )
    async def test_invalid_path_param_422(
        self,
        client: AsyncClient,
        admin_headers: dict,
        openapi_spec: dict,
        method: str,
        url: str,
        template: str,
    ):
        body = {} if method in ("post", "patch") else None
        response = await client.request(method, url, headers=admin_headers, json=body)
        assert_matches_openapi(response, template, method, openapi_spec)
        assert response.status_code == 422
