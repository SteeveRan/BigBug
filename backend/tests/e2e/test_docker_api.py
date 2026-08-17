"""
@file test_docker_api.py
@description E2E tests for the Docker Image HTTP API (/api/docker-images)
              against a live backend: auth, list, create-without-indexing
              (no external registry calls), 4xx for missing sources, tags/logs,
              and the pure-parsing /analyze endpoint. No mocks, no sqlite.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestDockerSources:
    async def test_list_sources_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/docker-images")
        assert response.status_code == 401

    async def test_list_sources(self, client: AsyncClient, admin_headers: dict, openapi_spec: dict):
        response = await client.get("/api/docker-images", headers=admin_headers)
        assert_matches_openapi(response, "/api/docker-images", "get", openapi_spec)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_source_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.get("/api/docker-images/999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_create_source_without_indexing(
        self, client: AsyncClient, admin_headers: dict, unique_name: str, openapi_spec: dict
    ):
        """POST without image_name only stores the source — no registry fetch."""
        name = f"docker-{unique_name}"
        response = await client.post(
            "/api/docker-images",
            headers=admin_headers,
            json={"name": name, "registry_url": "https://registry.example.com"},
        )
        assert_matches_openapi(response, "/api/docker-images", "post", openapi_spec)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == name
        assert data["registry_url"] == "https://registry.example.com/v2"
        assert data["status_flag"] == 4  # pending — no indexing happened

        await client.delete(f"/api/docker-images/{data['id']}", headers=admin_headers)

    async def test_create_source_duplicate_name(
        self, client: AsyncClient, admin_headers: dict, unique_name: str
    ):
        name = f"docker-dup-{unique_name}"
        first = await client.post(
            "/api/docker-images",
            headers=admin_headers,
            json={"name": name, "registry_url": "https://registry.example.com"},
        )
        assert first.status_code == 201
        try:
            second = await client.post(
                "/api/docker-images",
                headers=admin_headers,
                json={"name": name, "registry_url": "https://registry.other.com"},
            )
            assert second.status_code == 400
        finally:
            await client.delete(f"/api/docker-images/{first.json()['id']}", headers=admin_headers)

    async def test_update_source_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.patch(
            "/api/docker-images/999999",
            headers=admin_headers,
            json={"description": "nope"},
        )
        assert response.status_code == 404

    async def test_delete_source_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.delete("/api/docker-images/999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_index_source_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.post(
            "/api/docker-images/999999/index?image_name=nginx",
            headers=admin_headers,
        )
        assert response.status_code == 404


class TestDockerSourceDetails:
    @pytest.fixture
    async def source(self, client: AsyncClient, admin_headers: dict, unique_name: str) -> dict:
        response = await client.post(
            "/api/docker-images",
            headers=admin_headers,
            json={
                "name": f"docker-tags-{unique_name}",
                "registry_url": "https://registry.example.com",
            },
        )
        assert response.status_code == 201
        yield response.json()
        await client.delete(f"/api/docker-images/{response.json()['id']}", headers=admin_headers)

    async def test_list_tags_empty(
        self, client: AsyncClient, admin_headers: dict, source: dict, openapi_spec: dict
    ):
        response = await client.get(
            f"/api/docker-images/{source['id']}/tags", headers=admin_headers
        )
        assert_matches_openapi(response, "/api/docker-images/{source_id}/tags", "get", openapi_spec)
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_logs_empty(
        self, client: AsyncClient, admin_headers: dict, source: dict, openapi_spec: dict
    ):
        response = await client.get(
            f"/api/docker-images/{source['id']}/logs", headers=admin_headers
        )
        assert_matches_openapi(response, "/api/docker-images/{source_id}/logs", "get", openapi_spec)
        assert response.status_code == 200
        assert response.json() == []


class TestDockerSourceValidation:
    """Documented 422 validation paths (invalid integer path params)."""

    @pytest.mark.parametrize(
        ("method", "url", "template"),
        [
            ("get", "/api/docker-images/abc", "/api/docker-images/{source_id}"),
            ("patch", "/api/docker-images/abc", "/api/docker-images/{source_id}"),
            ("delete", "/api/docker-images/abc", "/api/docker-images/{source_id}"),
            ("post", "/api/docker-images/abc/index", "/api/docker-images/{source_id}/index"),
            ("post", "/api/docker-images/abc/mirror", "/api/docker-images/{source_id}/mirror"),
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


class TestAnalyzeImage:
    async def test_analyze_requires_auth(self, client: AsyncClient):
        response = await client.post(
            "/api/docker-images/analyze", json={"image_name": "nginx:latest"}
        )
        assert response.status_code == 401

    async def test_analyze_image(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        """Pure parsing — no external call. Returns registry-match suggestions."""
        response = await client.post(
            "/api/docker-images/analyze",
            headers=admin_headers,
            json={"image_name": "nginx:latest"},
        )
        assert_matches_openapi(response, "/api/docker-images/analyze", "post", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert data["image_name"] == "nginx:latest"
        assert isinstance(data["compatible_registries"], list)
