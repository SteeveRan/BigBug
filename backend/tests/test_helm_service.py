"""
@file test_helm_service.py
@description Unit tests for HelmService — import_source_from_url, index_source,
             _fetch_index, _sync_chart_entries, _normalize_repo_url.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ExternalServiceError
from app.models.helm_chart_source import HelmChartSource
from app.models.helm_chart_version import HelmChartVersion
from app.services.helm import HelmService, _normalize_repo_url, _validate_repo_url


FAKE_INDEX_YAML = """
apiVersion: v1
entries:
  nginx:
    - apiVersion: v2
      name: nginx
      version: 15.1.0
      appVersion: 1.27.0
      description: NGINX web server
      digest: sha256:abc123def456
      urls:
        - https://charts.example.com/nginx-15.1.0.tgz
    - apiVersion: v2
      name: nginx
      version: 15.0.0
      appVersion: 1.26.0
      description: NGINX web server
      digest: sha256:old-digest-789
      urls:
        - https://charts.example.com/nginx-15.0.0.tgz
  redis:
    - apiVersion: v2
      name: redis
      version: 18.0.0
      appVersion: 7.4.0
      description: Redis in-memory database
      digest: sha256:redis-digest-001
      urls:
        - https://charts.example.com/redis-18.0.0.tgz
"""


@pytest.fixture
def helm_service() -> HelmService:
    return HelmService()


# ─── _normalize_repo_url ────────────────────────────────────────────────────


class TestNormalizeRepoUrl:
    def test_adds_index_yaml_when_missing(self):
        assert _normalize_repo_url("https://charts.example.com") == (
            "https://charts.example.com/index.yaml"
        )

    def test_strips_trailing_slash_then_adds_index_yaml(self):
        assert _normalize_repo_url("https://charts.example.com/") == (
            "https://charts.example.com/index.yaml"
        )

    def test_preserves_existing_index_yaml(self):
        url = "https://charts.example.com/index.yaml"
        assert _normalize_repo_url(url) == url


# ─── _validate_repo_url ─────────────────────────────────────────────────────


class TestValidateRepoUrl:
    def test_valid_http_url(self):
        _validate_repo_url("http://charts.local")

    def test_valid_https_url(self):
        _validate_repo_url("https://charts.example.com/bitnami")

    def test_invalid_no_scheme(self):
        with pytest.raises(BadRequestError, match="must start with http"):
            _validate_repo_url("ftp://charts.example.com")


# ─── _fetch_index ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_index_success(helm_service):
    """_fetch_index downloads and parses a valid index.yaml."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = FAKE_INDEX_YAML
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        index = await helm_service._fetch_index("https://charts.example.com/index.yaml")

    assert "entries" in index
    assert "nginx" in index["entries"]
    assert len(index["entries"]["nginx"]) == 2


@pytest.mark.asyncio
async def test_fetch_index_network_error(helm_service):
    """Network errors are wrapped in ExternalServiceError."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client_cls.return_value = mock_client

        with pytest.raises(ExternalServiceError, match="Helm repo"):
            await helm_service._fetch_index("https://down.example.com/index.yaml")


@pytest.mark.asyncio
async def test_fetch_index_no_entries_key(helm_service):
    """A YAML response without 'entries' raises ExternalServiceError."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "apiVersion: v1\nother: data\n"
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(ExternalServiceError, match="entries"):
            await helm_service._fetch_index("https://bad.example.com/index.yaml")


# ─── index_source ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_index_source_creates_versions(helm_service, db_session: AsyncSession):
    """index_source parses index.yaml and creates HelmChartVersion records."""
    source = HelmChartSource(
        name="test-source", repo_url="https://charts.example.com/index.yaml"
    )
    db_session.add(source)
    await db_session.commit()

    with patch.object(helm_service, "_fetch_index") as mock_fetch:
        mock_fetch.return_value = {
            "entries": {
                "nginx": [
                    {
                        "version": "15.1.0",
                        "appVersion": "1.27.0",
                        "description": "NGINX web server",
                        "digest": "sha256:abc123",
                        "urls": ["https://charts.example.com/nginx-15.1.0.tgz"],
                    }
                ]
            }
        }

        sync_log = await helm_service.index_source(source, db_session)

    assert sync_log.status_flag == 0  # success
    assert source.status_flag == 0

    result = await db_session.execute(
        select(HelmChartVersion).where(HelmChartVersion.source_id == source.id)
    )
    versions = result.scalars().all()
    assert len(versions) == 1
    assert versions[0].chart_name == "nginx"
    assert versions[0].version == "15.1.0"


@pytest.mark.asyncio
async def test_sync_chart_entries_idempotent(helm_service, db_session: AsyncSession):
    """Re-indexing the same entries updates existing records instead of duplicating."""
    source = HelmChartSource(
        name="idempotent-source",
        repo_url="https://charts.example.com/index.yaml",
    )
    db_session.add(source)
    await db_session.commit()

    entries = {
        "nginx": [
            {
                "version": "15.1.0",
                "appVersion": "1.27.0",
                "description": "NGINX v1",
                "digest": "sha256:first",
                "urls": ["https://charts.example.com/nginx-15.1.0.tgz"],
            }
        ]
    }

    # First sync
    with patch.object(helm_service, "_fetch_index", return_value={"entries": entries}):
        await helm_service.index_source(source, db_session)

    # Second sync with updated digest
    entries["nginx"][0]["digest"] = "sha256:updated"
    with patch.object(helm_service, "_fetch_index", return_value={"entries": entries}):
        await helm_service.index_source(source, db_session)

    result = await db_session.execute(
        select(HelmChartVersion).where(HelmChartVersion.source_id == source.id)
    )
    versions = result.scalars().all()
    assert len(versions) == 1
    assert versions[0].digest == "sha256:updated"


@pytest.mark.asyncio
async def test_index_source_fetch_failure(helm_service, db_session: AsyncSession):
    """When _fetch_index fails, source and log are marked as failed."""
    source = HelmChartSource(
        name="fail-source", repo_url="https://charts.example.com/index.yaml"
    )
    db_session.add(source)
    await db_session.commit()

    with patch.object(helm_service, "_fetch_index") as mock_fetch:
        mock_fetch.side_effect = ExternalServiceError("Helm repo", "network error")
        sync_log = await helm_service.index_source(source, db_session)

    assert sync_log.status_flag == 1  # failed
    assert source.status_flag == 1


# ─── import_source_from_url ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_source_from_url(helm_service, db_session: AsyncSession):
    """import_source_from_url creates a source and indexes it."""
    with patch.object(helm_service, "_fetch_index") as mock_fetch:
        mock_fetch.return_value = {
            "entries": {
                "redis": [
                    {
                        "version": "18.0.0",
                        "appVersion": "7.4.0",
                        "description": "Redis",
                        "digest": "sha256:redis-001",
                        "urls": ["https://charts.example.com/redis-18.0.0.tgz"],
                    }
                ]
            }
        }

        source = await helm_service.import_source_from_url(
            "new-helm-source",
            "https://charts.new.com",
            db_session,
        )

    assert source.name == "new-helm-source"
    assert source.repo_url == "https://charts.new.com/index.yaml"
    assert source.status_flag == 0  # success after indexing

    # Verify version was created
    result = await db_session.execute(
        select(HelmChartVersion).where(HelmChartVersion.source_id == source.id)
    )
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_import_source_duplicate_name(helm_service, db_session: AsyncSession):
    """Creating a source with a duplicate name raises BadRequestError."""
    source = HelmChartSource(
        name="duplicate-test", repo_url="https://charts.example.com/index.yaml"
    )
    db_session.add(source)
    await db_session.commit()

    with pytest.raises(BadRequestError, match="already exists"):
        await helm_service.import_source_from_url(
            "duplicate-test",
            "https://charts.other.com",
            db_session,
        )
