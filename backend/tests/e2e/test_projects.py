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

    async def test_get_project_not_found(
        self, client: AsyncClient, admin_headers: dict
    ):
        response = await client.get("/api/projects/999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_update_project_not_found(
        self, client: AsyncClient, admin_headers: dict
    ):
        response = await client.patch(
            "/api/projects/999999",
            headers=admin_headers,
            json={"custom_description": "nope"},
        )
        assert response.status_code == 404

    async def test_delete_project_not_found(
        self, client: AsyncClient, admin_headers: dict
    ):
        response = await client.delete("/api/projects/999999", headers=admin_headers)
        assert response.status_code == 404
