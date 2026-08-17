"""
@file test_pipelines.py
@description E2E tests for Pipeline Runs (/api/pipelines) and GitLab Components
              (/api/components) against a live backend: list/auth, 404 for
              missing runs/components, and RBAC 403 for the viewer. Triggering
              a run and running a component hit GitLab, so only permission
              boundaries and read paths are exercised. No mocks, no sqlite.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestPipelineRunsAPI:
    async def test_list_pipelines_unauthenticated(self, client: AsyncClient):
        response = await client.get("/api/pipelines")
        assert response.status_code == 401

    async def test_list_pipelines(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/pipelines", headers=admin_headers)
        assert_matches_openapi(response, "/api/pipelines", "get", openapi_spec)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    async def test_get_pipeline_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.get("/api/pipelines/999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_trigger_pipeline_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        response = await client.post(
            "/api/pipelines",
            json={"provider_id": 1, "gitlab_project_id": 1, "ref": "main"},
            headers=viewer_headers,
        )
        assert response.status_code == 403

    async def test_cancel_pipeline_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        response = await client.post("/api/pipelines/1/cancel", headers=viewer_headers)
        assert response.status_code == 403

    async def test_retry_pipeline_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        response = await client.post("/api/pipelines/1/retry", headers=viewer_headers)
        assert response.status_code == 403

    async def test_list_pipeline_configs(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/pipelines/configs", headers=admin_headers)
        assert_matches_openapi(response, "/api/pipelines/configs", "get", openapi_spec)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestPipelineRunsValidation:
    """Documented 422 validation paths (invalid path params / empty body)."""

    @pytest.mark.parametrize(
        ("method", "url", "template"),
        [
            ("get", "/api/pipelines/abc", "/api/pipelines/{run_id}"),
            ("post", "/api/pipelines/abc/cancel", "/api/pipelines/{run_id}/cancel"),
            ("post", "/api/pipelines/abc/retry", "/api/pipelines/{run_id}/retry"),
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
        body = {} if method == "post" else None
        response = await client.request(method, url, headers=admin_headers, json=body)
        assert_matches_openapi(response, template, method, openapi_spec)
        assert response.status_code == 422

    async def test_create_empty_body_422(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.post("/api/pipelines", headers=admin_headers, json={})
        assert_matches_openapi(response, "/api/pipelines", "post", openapi_spec)
        assert response.status_code == 422


class TestGitLabComponentsAPI:
    async def test_list_components(
        self, client: AsyncClient, admin_headers: dict, openapi_spec: dict
    ):
        response = await client.get("/api/components", headers=admin_headers)
        assert_matches_openapi(response, "/api/components", "get", openapi_spec)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_component_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        response = await client.post(
            "/api/components",
            json={
                "name": "e2e-component",
                "provider_id": 1,
                "project_path": "group/project",
                "component_path": ".gitlab/components/test.yml",
            },
            headers=viewer_headers,
        )
        assert response.status_code == 403

    async def test_get_component_not_found(self, client: AsyncClient, admin_headers: dict):
        response = await client.get("/api/components/999999", headers=admin_headers)
        assert response.status_code == 404

    async def test_delete_component_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        response = await client.delete("/api/components/1", headers=viewer_headers)
        assert response.status_code == 403
