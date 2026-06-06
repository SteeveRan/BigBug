"""
@file test_docker_service.py
@description Unit tests for DockerRegistryService — import_source_from_url,
             index_source, _fetch_tags, _resolve_manifest_digest,
             _normalize_registry_url.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ExternalServiceError
from app.models.docker_image_source import DockerImageSource
from app.models.docker_image_tag import DockerImageTag
from app.services.docker import (
    DockerRegistryService,
    _normalize_registry_url,
    _validate_registry_url,
)

FAKE_TAGS_RESPONSE = {
    "name": "library/nginx",
    "tags": ["1.27-alpine", "1.26", "latest"],
}


@pytest.fixture
def docker_service() -> DockerRegistryService:
    return DockerRegistryService()


# ─── _normalize_registry_url ────────────────────────────────────────────────


class TestNormalizeRegistryUrl:
    def test_adds_v2_when_missing(self):
        assert _normalize_registry_url("https://registry-1.docker.io") == (
            "https://registry-1.docker.io/v2"
        )

    def test_strips_trailing_slash_then_adds_v2(self):
        assert _normalize_registry_url("https://registry.example.com/") == (
            "https://registry.example.com/v2"
        )

    def test_preserves_existing_v2_suffix(self):
        url = "https://registry.local/v2"
        assert _normalize_registry_url(url) == url


# ─── _validate_registry_url ─────────────────────────────────────────────────


class TestValidateRegistryUrl:
    def test_valid_url(self):
        _validate_registry_url("https://registry.example.com")

    def test_invalid_no_scheme(self):
        with pytest.raises(BadRequestError, match="must start with http"):
            _validate_registry_url("ftp://registry.local")


# ─── _resolve_manifest_digest ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_manifest_digest(docker_service):
    """A 200 HEAD response with docker-content-digest returns the digest."""
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"docker-content-digest": "sha256:abc123"}
    mock_response.raise_for_status = MagicMock()
    mock_client.head = AsyncMock(return_value=mock_response)

    digest = await docker_service._resolve_manifest_digest(
        mock_client, "https://registry.local/v2", "library/nginx", "latest"
    )
    assert digest == "sha256:abc123"


@pytest.mark.asyncio
async def test_resolve_manifest_digest_404(docker_service):
    """A 404 response returns None."""
    mock_client = MagicMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_client.head = AsyncMock(return_value=mock_response)

    digest = await docker_service._resolve_manifest_digest(
        mock_client, "https://registry.local/v2", "missing/image", "latest"
    )
    assert digest is None


# ─── _fetch_tags ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_tags_success(docker_service):
    """_fetch_tags returns the parsed JSON response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = FAKE_TAGS_RESPONSE
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        tags_data = await docker_service._fetch_tags("https://registry.local/v2", "library/nginx")

    assert tags_data == FAKE_TAGS_RESPONSE
    assert "tags" in tags_data


@pytest.mark.asyncio
async def test_fetch_tags_404(docker_service):
    """A non-200 response raises ExternalServiceError."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=MagicMock(status_code=404)
        )
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ExternalServiceError, match="Docker registry"):
            await docker_service._fetch_tags("https://registry.local/v2", "nonexistent")


@pytest.mark.asyncio
async def test_fetch_tags_no_tags_key(docker_service):
    """A response without 'tags' raises ExternalServiceError."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"other": "data"}
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ExternalServiceError, match="tags"):
            await docker_service._fetch_tags("https://registry.local/v2", "no-tags-image")


# ─── index_source ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_source_creates_tags(docker_service, db_session: AsyncSession):
    """index_source fetches tags and creates DockerImageTag records."""
    source = DockerImageSource(
        name="docker-test-source",
        registry_url="https://registry.local/v2",
    )
    db_session.add(source)
    await db_session.commit()

    with patch.object(docker_service, "_fetch_tags") as mock_fetch:
        mock_fetch.return_value = {
            "name": "library/nginx",
            "tags": ["1.27-alpine", "latest"],
        }

        # Also need to mock _resolve_manifest_digest since index_source calls it
        with patch.object(docker_service, "_resolve_manifest_digest") as mock_digest:
            mock_digest.return_value = "sha256:test-digest"

            sync_log = await docker_service.index_source(source, "library/nginx", db_session)

    assert sync_log.status_flag == 0  # success
    assert source.status_flag == 0

    result = await db_session.execute(
        select(DockerImageTag).where(DockerImageTag.source_id == source.id)
    )
    tags = result.scalars().all()
    assert len(tags) == 2
    tag_names = {t.tag for t in tags}
    assert tag_names == {"1.27-alpine", "latest"}


@pytest.mark.asyncio
async def test_sync_tags_idempotent(docker_service, db_session: AsyncSession):
    """Re-indexing the same image updates existing tags instead of duplicating."""
    source = DockerImageSource(
        name="idempotent-docker",
        registry_url="https://registry.local/v2",
    )
    db_session.add(source)
    await db_session.commit()

    tags_data = {"name": "library/nginx", "tags": ["1.27-alpine"]}

    # First sync
    with (
        patch.object(docker_service, "_fetch_tags", return_value=tags_data),
        patch.object(docker_service, "_resolve_manifest_digest", return_value="sha256:old"),
    ):
        await docker_service.index_source(source, "library/nginx", db_session)

    # Second sync with updated digest
    with (
        patch.object(docker_service, "_fetch_tags", return_value=tags_data),
        patch.object(docker_service, "_resolve_manifest_digest", return_value="sha256:new"),
    ):
        await docker_service.index_source(source, "library/nginx", db_session)

    result = await db_session.execute(
        select(DockerImageTag).where(DockerImageTag.source_id == source.id)
    )
    tags = result.scalars().all()
    assert len(tags) == 1
    assert tags[0].digest == "sha256:new"


@pytest.mark.asyncio
async def test_index_source_fetch_failure(docker_service, db_session: AsyncSession):
    """When _fetch_tags fails, source and log are marked as failed."""
    source = DockerImageSource(
        name="fail-docker-source",
        registry_url="https://registry.local/v2",
    )
    db_session.add(source)
    await db_session.commit()

    with patch.object(docker_service, "_fetch_tags") as mock_fetch:
        mock_fetch.side_effect = ExternalServiceError("Docker registry", "network error")
        sync_log = await docker_service.index_source(source, "library/nginx", db_session)

    assert sync_log.status_flag == 1  # failed
    assert source.status_flag == 1


# ─── import_source_from_url ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_source_from_url_no_image(docker_service, db_session: AsyncSession):
    """Creating a source without image_name succeeds without indexing."""
    source = await docker_service.import_source_from_url(
        "registry-only",
        "https://registry.example.com",
        image_name=None,
        db=db_session,
    )

    assert source.name == "registry-only"
    assert source.registry_url == "https://registry.example.com/v2"
    assert source.status_flag == 4  # pending (no indexing happened)


@pytest.mark.asyncio
async def test_import_source_from_url_with_image(docker_service, db_session: AsyncSession):
    """Creating a source with image_name triggers indexing."""
    with patch.object(docker_service, "_fetch_tags") as mock_fetch:
        mock_fetch.return_value = {"name": "library/alpine", "tags": ["3.19"]}
        with patch.object(docker_service, "_resolve_manifest_digest", return_value="sha256:abc"):
            source = await docker_service.import_source_from_url(
                "alpine-registry",
                "https://registry.example.com",
                image_name="library/alpine",
                db=db_session,
            )

    assert source.name == "alpine-registry"
    assert source.status_flag == 0  # success after indexing


@pytest.mark.asyncio
async def test_import_source_duplicate_name(docker_service, db_session: AsyncSession):
    """Creating a source with a duplicate name raises BadRequestError."""
    source = DockerImageSource(name="dupe-docker", registry_url="https://registry.local/v2")
    db_session.add(source)
    await db_session.commit()

    with pytest.raises(BadRequestError, match="already exists"):
        await docker_service.import_source_from_url(
            "dupe-docker",
            "https://registry.other.com",
            image_name=None,
            db=db_session,
        )
