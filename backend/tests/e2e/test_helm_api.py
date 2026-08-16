"""
@file test_helm_api.py
@description E2E tests for the Helm Chart HTTP API (/api/helm-charts) against a
              live backend. Helm source creation ALWAYS indexes the upstream
              repository (real external call), so these tests cover list/auth,
              4xx for missing sources, and empty versions/logs without creating
              a source. No mocks, no sqlite.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestHelmSources:
    async def test_list_sources_requires_auth(self, client: AsyncClient):
        response = await client.get("/api/helm-charts")
        assert response.status_code == 401

    async def test_list_sources(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/helm-charts", headers=admin_headers)
        assert_matches_openapi(response, "/api/helm-charts", "get", openapi_spec)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_source_not_found(
        self, client: AsyncClient, admin_headers: dict
    ):
        response = await client.get("/api/helm-charts/999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_update_source_not_found(
        self, client: AsyncClient, admin_headers: dict
    ):
        response = await client.patch(
            "/api/helm-charts/999999",
            headers=admin_headers,
            json={"description": "nope"},
        )
        assert response.status_code == 404

    async def test_delete_source_not_found(
        self, client: AsyncClient, admin_headers: dict
    ):
        response = await client.delete("/api/helm-charts/999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_index_source_not_found(
        self, client: AsyncClient, admin_headers: dict
    ):
        response = await client.post("/api/helm-charts/999999/index", headers=admin_headers)
        assert response.status_code == 404

    async def test_versions_empty_for_missing_source(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get(
            "/api/helm-charts/999999/versions", headers=admin_headers
        )
        assert_matches_openapi(
            response, "/api/helm-charts/{source_id}/versions", "get", openapi_spec
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_logs_empty_for_missing_source(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get(
            "/api/helm-charts/999999/logs", headers=admin_headers
        )
        assert_matches_openapi(
            response, "/api/helm-charts/{source_id}/logs", "get", openapi_spec
        )
        assert response.status_code == 200
        assert response.json() == []
