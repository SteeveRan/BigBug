"""
@file test_helm_api.py
@description Integration tests for Helm Chart HTTP API endpoints
             (/api/helm-charts) — CRUD, index, versions, logs.
"""

from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.helm_chart_source import HelmChartSource
from app.models.helm_chart_version import HelmChartVersion

pytestmark = pytest.mark.e2e


@pytest_asyncio.fixture
async def sample_helm_source(db_session: AsyncSession):
    """Create a sample HelmChartSource with one version for tests."""
    source = HelmChartSource(
        name="bitnami-test",
        repo_url="https://charts.bitnami.com/bitnami/index.yaml",
        status_flag=0,
        status_text="ok",
    )
    db_session.add(source)
    await db_session.flush()

    version = HelmChartVersion(
        source_id=source.id,
        chart_name="nginx",
        version="15.1.0",
        app_version="1.27.0",
        description="NGINX web server",
        digest="sha256:abc123",
        is_synced=True,
        status_flag=0,
        status_text="ok",
    )
    db_session.add(version)
    await db_session.commit()
    await db_session.refresh(source)
    return source


# ─── List sources ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_helm_sources(client: AsyncClient, operator_token: str, sample_helm_source):
    """GET /api/helm-charts returns list of sources (operator can access)."""
    response = await client.get(
        "/api/helm-charts",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "bitnami-test"


@pytest.mark.asyncio
async def test_list_helm_sources_requires_auth(client: AsyncClient):
    """Unauthenticated access must be rejected."""
    response = await client.get("/api/helm-charts")
    assert response.status_code == 401


# ─── Get source ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_helm_source(client: AsyncClient, operator_token: str, sample_helm_source):
    """GET /api/helm-charts/{id} returns source with versions."""
    response = await client.get(
        f"/api/helm-charts/{sample_helm_source.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "bitnami-test"
    assert "versions" in data
    assert len(data["versions"]) >= 1


@pytest.mark.asyncio
async def test_get_helm_source_not_found(client: AsyncClient, operator_token: str):
    """Non-existent source returns 404."""
    response = await client.get(
        "/api/helm-charts/99999",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 404


# ─── Create source ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_helm_source(client: AsyncClient, operator_token: str):
    """POST /api/helm-charts creates a new source and indexes it."""
    with patch("app.services.helm.HelmService._fetch_index") as mock_fetch:
        mock_fetch.return_value = {
            "entries": {
                "redis": [
                    {
                        "version": "18.0.0",
                        "appVersion": "7.4.0",
                        "description": "Redis",
                        "digest": "sha256:redis",
                        "urls": ["https://charts.example.com/redis-18.0.0.tgz"],
                    }
                ]
            }
        }

        response = await client.post(
            "/api/helm-charts",
            headers={"Authorization": f"Bearer {operator_token}"},
            json={
                "name": "redis-charts",
                "repo_url": "https://charts.example.com",
            },
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "redis-charts"
    assert data["status_flag"] == 0  # success after indexing


@pytest.mark.asyncio
async def test_create_helm_source_duplicate(
    client: AsyncClient, operator_token: str, sample_helm_source
):
    """Creating a source with existing name returns 400."""
    response = await client.post(
        "/api/helm-charts",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "name": "bitnami-test",
            "repo_url": "https://charts.other.com",
        },
    )
    assert response.status_code == 400


# ─── Update source ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_helm_source(client: AsyncClient, operator_token: str, sample_helm_source):
    """PATCH /api/helm-charts/{id} updates source fields."""
    response = await client.patch(
        f"/api/helm-charts/{sample_helm_source.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"description": "Updated chart source description"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated chart source description"


@pytest.mark.asyncio
async def test_update_helm_source_not_found(client: AsyncClient, operator_token: str):
    """Updating non-existent source returns 404."""
    response = await client.patch(
        "/api/helm-charts/99999",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"description": "test"},
    )
    assert response.status_code == 404


# ─── Delete source ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_helm_source(client: AsyncClient, operator_token: str, sample_helm_source):
    """DELETE /api/helm-charts/{id} removes the source (operator can delete)."""
    response = await client.delete(
        f"/api/helm-charts/{sample_helm_source.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_helm_source_not_found(client: AsyncClient, operator_token: str):
    """Deleting non-existent source returns 404."""
    response = await client.delete(
        "/api/helm-charts/99999",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 404


# ─── Index source ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_helm_source(client: AsyncClient, operator_token: str, sample_helm_source):
    """POST /api/helm-charts/{id}/index re-indexes the source."""
    with patch("app.services.helm.HelmService._fetch_index") as mock_fetch:
        mock_fetch.return_value = {
            "entries": {
                "nginx": [
                    {
                        "version": "15.2.0",
                        "appVersion": "1.28.0",
                        "description": "NGINX updated",
                        "digest": "sha256:new",
                        "urls": ["https://charts.example.com/nginx-15.2.0.tgz"],
                    }
                ]
            }
        }

        response = await client.post(
            f"/api/helm-charts/{sample_helm_source.id}/index",
            headers={"Authorization": f"Bearer {operator_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status_flag"] == 0  # success
    assert "Indexed 1 chart" in data["log_output"]


@pytest.mark.asyncio
async def test_index_helm_source_not_found(client: AsyncClient, operator_token: str):
    """Indexing non-existent source returns 404."""
    response = await client.post(
        "/api/helm-charts/99999/index",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 404


# ─── Versions ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_helm_versions(client: AsyncClient, operator_token: str, sample_helm_source):
    """GET /api/helm-charts/{id}/versions returns versions list."""
    response = await client.get(
        f"/api/helm-charts/{sample_helm_source.id}/versions",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["chart_name"] == "nginx"


@pytest.mark.asyncio
async def test_get_helm_versions_filter(
    client: AsyncClient, operator_token: str, sample_helm_source
):
    """Filtering by chart_name works."""
    response = await client.get(
        f"/api/helm-charts/{sample_helm_source.id}/versions?chart_name=nonexistent",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


# ─── Logs ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_helm_logs(client: AsyncClient, operator_token: str, sample_helm_source):
    """GET /api/helm-charts/{id}/logs returns sync log entries."""
    response = await client.get(
        f"/api/helm-charts/{sample_helm_source.id}/logs",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
