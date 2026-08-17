"""
@file test_projects.py
@description E2E tests for the legacy GitHub Projects API (/api/projects)
              against a live backend. Project creation/import/refresh hit the
              real GitHub API, so these tests cover auth, listing, and 4xx for
              missing projects only. No mocks, no sqlite.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestProjects:
    async def test_list_projects_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/projects")
        assert response.status_code == 401

    async def test_list_projects(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/projects", headers=admin_headers)
        assert_matches_openapi(response, "/api/projects", "get", openapi_spec)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_project_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.get("/api/projects/999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_update_project_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.patch(
            "/api/projects/999999",
            headers=admin_headers,
            json={"custom_description": "nope"},
        )
        assert response.status_code == 404

    async def test_delete_project_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.delete("/api/projects/999999", headers=admin_headers)
        assert response.status_code == 404


class TestProjectsValidation:
    """Documented 422 validation paths (invalid path params / empty body)."""

    @pytest.mark.parametrize(
        ("method", "url", "template"),
        [
            ("get", "/api/projects/abc", "/api/projects/{project_id}"),
            ("get", "/api/projects/abc/releases", "/api/projects/{project_id}/releases"),
            ("patch", "/api/projects/abc", "/api/projects/{project_id}"),
            ("delete", "/api/projects/abc", "/api/projects/{project_id}"),
            ("post", "/api/projects/abc/refresh", "/api/projects/{project_id}/refresh"),
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

    @pytest.mark.parametrize(
        ("url", "template"),
        [
            ("/api/projects", "/api/projects"),
            ("/api/projects/import", "/api/projects/import"),
        ],
    )
    async def test_create_empty_body_422(
        self,
        client: AsyncClient,
        admin_headers: dict,
        openapi_spec: dict,
        url: str,
        template: str,
    ):
        response = await client.post(url, headers=admin_headers, json={})
        assert_matches_openapi(response, template, "post", openapi_spec)
        assert response.status_code == 422
