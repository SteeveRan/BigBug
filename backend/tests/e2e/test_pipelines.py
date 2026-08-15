"""
@file test_pipelines.py
@description E2E tests for Pipeline Runs API and GitLab Components API.
@dependencies pytest, pytest-asyncio, backend/tests/conftest.py,
             backend/tests/e2e/conftest.py
@relatedFiles ../../app/api/pipelines.py, ../../app/api/components.py
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pipeline_run import PipelineRun

# ──────────────────────────────────────────────────────────────────────
# Pipeline Runs API
# ──────────────────────────────────────────────────────────────────────


class TestPipelineRunsAPI:
    """E2E tests for /api/pipelines endpoints."""

    @pytest_asyncio.fixture
    async def sample_run(self, db_session: AsyncSession) -> PipelineRun:
        """Create a sample pipeline run for GET / detail tests."""
        run = PipelineRun(
            provider_id=1,
            gitlab_project_id=42,
            gitlab_pipeline_id=100,
            ref="main",
            status_flag=0,
            status_text="OK",
            trigger_type="manual",
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)
        return run

    @pytest.mark.asyncio
    async def test_get_pipelines_authenticated(
        self, client: AsyncClient, auth_headers: dict, sample_run: PipelineRun
    ):
        """GET /api/pipelines returns list for authenticated user."""
        response = await client.get("/api/pipelines", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_get_pipelines_unauthenticated(self, client: AsyncClient):
        """GET /api/pipelines returns 401 or 403 for unauthenticated."""
        response = await client.get("/api/pipelines")
        assert response.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_get_pipeline_not_found(self, client: AsyncClient, auth_headers: dict):
        """GET /api/pipelines/99999 returns 404."""
        response = await client.get("/api/pipelines/99999", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_pipeline_detail(
        self, client: AsyncClient, auth_headers: dict, sample_run: PipelineRun
    ):
        """GET /api/pipelines/{id} returns run details."""
        response = await client.get(f"/api/pipelines/{sample_run.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_run.id
        assert data["ref"] == "main"
        assert data["status_flag"] == 0

    @pytest.mark.asyncio
    async def test_trigger_pipeline_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        """POST /api/pipelines returns 403 for viewer without pipelines:write."""
        response = await client.post(
            "/api/pipelines",
            json={
                "provider_id": 1,
                "gitlab_project_id": 1,
                "ref": "main",
            },
            headers=viewer_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_cancel_pipeline_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        """POST /api/pipelines/{id}/cancel returns 403 for viewer."""
        response = await client.post("/api/pipelines/1/cancel", headers=viewer_headers)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_retry_pipeline_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        """POST /api/pipelines/{id}/retry returns 403 for viewer."""
        response = await client.post("/api/pipelines/1/retry", headers=viewer_headers)
        assert response.status_code == 403


# ──────────────────────────────────────────────────────────────────────
# GitLab Components API
# ──────────────────────────────────────────────────────────────────────


class TestGitLabComponentsAPI:
    """E2E tests for /api/components endpoints."""

    @pytest.mark.asyncio
    async def test_get_components_authenticated(self, client: AsyncClient, auth_headers: dict):
        """GET /api/components returns list."""
        response = await client.get("/api/components", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_create_component_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        """POST /api/components returns 403 for viewer."""
        response = await client.post(
            "/api/components",
            json={
                "name": "test-component",
                "provider_id": 1,
                "project_path": "group/project",
                "component_path": ".gitlab/components/test.yml",
            },
            headers=viewer_headers,
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_component_not_found(self, client: AsyncClient, auth_headers: dict):
        """GET /api/components/99999 returns 404."""
        response = await client.get("/api/components/99999", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_component_requires_permission(
        self, client: AsyncClient, viewer_headers: dict
    ):
        """DELETE /api/components/1 returns 403 for viewer."""
        response = await client.delete("/api/components/1", headers=viewer_headers)
        assert response.status_code == 403
