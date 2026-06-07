"""
@file test_docker_api.py
@description Integration tests for Docker Image HTTP API endpoints
             (/api/docker-images) — CRUD, index, tags, logs.
"""

from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.docker_image_source import DockerImageSource
from app.models.docker_image_tag import DockerImageTag

pytestmark = pytest.mark.e2e


@pytest_asyncio.fixture
async def sample_docker_source(db_session: AsyncSession):
    """Create a sample DockerImageSource with one tag for tests."""
    source = DockerImageSource(
        name="docker-hub-test",
        registry_url="https://registry-1.docker.io/v2",
        status_flag=0,
        status_text="ok",
    )
    db_session.add(source)
    await db_session.flush()

    tag = DockerImageTag(
        source_id=source.id,
        image_name="library/nginx",
        tag="1.27-alpine",
        digest="sha256:abc123",
        is_synced=True,
        status_flag=0,
        status_text="ok",
    )
    db_session.add(tag)
    await db_session.commit()
    await db_session.refresh(source)
    return source


# ─── List sources ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_docker_sources(client: AsyncClient, operator_token: str, sample_docker_source):
    """GET /api/docker-images returns list of sources."""
    response = await client.get(
        "/api/docker-images",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["name"] == "docker-hub-test"


@pytest.mark.asyncio
async def test_list_docker_sources_requires_auth(client: AsyncClient):
    """Unauthenticated access must be rejected."""
    response = await client.get("/api/docker-images")
    assert response.status_code == 401


# ─── Get source ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_docker_source(client: AsyncClient, operator_token: str, sample_docker_source):
    """GET /api/docker-images/{id} returns source with tags."""
    response = await client.get(
        f"/api/docker-images/{sample_docker_source.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "docker-hub-test"
    assert "tags" in data
    assert len(data["tags"]) >= 1
    assert data["tags"][0]["tag"] == "1.27-alpine"


@pytest.mark.asyncio
async def test_get_docker_source_not_found(client: AsyncClient, operator_token: str):
    """Non-existent source returns 404."""
    response = await client.get(
        "/api/docker-images/99999",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 404


# ─── Create source ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_docker_source(client: AsyncClient, operator_token: str):
    """POST /api/docker-images creates a new source without indexing (no image_name)."""
    response = await client.post(
        "/api/docker-images",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "name": "alpine-registry",
            "registry_url": "https://registry.example.com",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "alpine-registry"
    assert data["registry_url"] == "https://registry.example.com/v2"


@pytest.mark.asyncio
async def test_create_docker_source_with_image_name(client: AsyncClient, operator_token: str):
    """POST /api/docker-images with image_name triggers indexing."""
    with patch("app.services.docker.DockerRegistryService._fetch_tags") as mock_fetch:
        mock_fetch.return_value = {"name": "library/alpine", "tags": ["3.19", "3.20"]}
        with patch(
            "app.services.docker.DockerRegistryService._resolve_manifest_digest"
        ) as mock_digest:
            mock_digest.return_value = "sha256:def456"

            response = await client.post(
                "/api/docker-images",
                headers={"Authorization": f"Bearer {operator_token}"},
                json={
                    "name": "alpine-with-tags",
                    "registry_url": "https://registry.example.com",
                    "image_name": "library/alpine",
                },
            )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "alpine-with-tags"
    assert data["status_flag"] == 0  # success after indexing


@pytest.mark.asyncio
async def test_create_docker_source_duplicate(
    client: AsyncClient, operator_token: str, sample_docker_source
):
    """Creating a source with existing name returns 400."""
    response = await client.post(
        "/api/docker-images",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "name": "docker-hub-test",
            "registry_url": "https://registry.other.com",
        },
    )
    assert response.status_code == 400


# ─── Update source ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_docker_source(client: AsyncClient, operator_token: str, sample_docker_source):
    """PATCH /api/docker-images/{id} updates source fields."""
    response = await client.patch(
        f"/api/docker-images/{sample_docker_source.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"description": "Updated docker registry description"},
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Updated docker registry description"


@pytest.mark.asyncio
async def test_update_docker_source_not_found(client: AsyncClient, operator_token: str):
    """Updating non-existent source returns 404."""
    response = await client.patch(
        "/api/docker-images/99999",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={"description": "test"},
    )
    assert response.status_code == 404


# ─── Delete source ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_docker_source(client: AsyncClient, operator_token: str, sample_docker_source):
    """DELETE /api/docker-images/{id} removes the source."""
    response = await client.delete(
        f"/api/docker-images/{sample_docker_source.id}",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_docker_source_not_found(client: AsyncClient, operator_token: str):
    """Deleting non-existent source returns 404."""
    response = await client.delete(
        "/api/docker-images/99999",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 404


# ─── Index source ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_docker_source_with_image_name(
    client: AsyncClient, operator_token: str, sample_docker_source
):
    """POST /api/docker-images/{id}/index?image_name=nginx indexes tags."""
    with patch("app.services.docker.DockerRegistryService._fetch_tags") as mock_fetch:
        mock_fetch.return_value = {
            "name": "library/nginx",
            "tags": ["1.27-alpine", "latest"],
        }
        with patch(
            "app.services.docker.DockerRegistryService._resolve_manifest_digest"
        ) as mock_digest:
            mock_digest.return_value = "sha256:indexed"

            response = await client.post(
                f"/api/docker-images/{sample_docker_source.id}/index?image_name=library%2Fnginx",
                headers={"Authorization": f"Bearer {operator_token}"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status_flag"] == 0  # success
    assert "Indexed 2 tag" in data["log_output"]


@pytest.mark.asyncio
async def test_index_docker_source_not_found(client: AsyncClient, operator_token: str):
    """Indexing non-existent source returns 404."""
    response = await client.post(
        "/api/docker-images/99999/index?image_name=nginx",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 404


# ─── Tags ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_docker_tags(client: AsyncClient, operator_token: str, sample_docker_source):
    """GET /api/docker-images/{id}/tags returns tags list."""
    response = await client.get(
        f"/api/docker-images/{sample_docker_source.id}/tags",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["tag"] == "1.27-alpine"


@pytest.mark.asyncio
async def test_get_docker_tags_filter(
    client: AsyncClient, operator_token: str, sample_docker_source
):
    """Filtering by image_name works."""
    response = await client.get(
        f"/api/docker-images/{sample_docker_source.id}/tags?image_name=nonexistent",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 0


# ─── Logs ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_docker_logs(client: AsyncClient, operator_token: str, sample_docker_source):
    """GET /api/docker-images/{id}/logs returns sync log entries."""
    response = await client.get(
        f"/api/docker-images/{sample_docker_source.id}/logs",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
