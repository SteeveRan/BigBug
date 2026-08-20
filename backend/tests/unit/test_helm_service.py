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

from app.core.exceptions import BadRequestError, ExternalServiceError, NotFoundError
from app.models.helm_chart_source import HelmChartSource
from app.models.helm_chart_version import HelmChartVersion
from app.models.helm_sync_log import HelmSyncLog
from app.services.helm import (
    HelmService,
    _normalize_repo_url,
    _validate_repo_url,
    mark_helm_version_synced,
)

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
    source = HelmChartSource(name="test-source", repo_url="https://charts.example.com/index.yaml")
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
    source = HelmChartSource(name="fail-source", repo_url="https://charts.example.com/index.yaml")
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


# ─── Index does NOT mark synced (mirror-only semantics) ─────────────────────


@pytest.mark.asyncio
async def test_index_source_does_not_mark_versions_synced(helm_service, db_session: AsyncSession):
    """Indexing records versions as pending; is_synced stays False."""
    source = HelmChartSource(
        name="pending-source",
        repo_url="https://charts.example.com/index.yaml",
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
                        "description": "NGINX",
                        "digest": "sha256:abc",
                        "urls": ["https://charts.example.com/nginx-15.1.0.tgz"],
                    }
                ]
            }
        }
        await helm_service.index_source(source, db_session)

    result = await db_session.execute(
        select(HelmChartVersion).where(HelmChartVersion.source_id == source.id)
    )
    version = result.scalar_one()
    assert version.is_synced is False
    assert version.status_flag == 4  # pending
    assert version.status_text == "pending"


# ─── mark_helm_version_synced ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mark_helm_version_synced_flips_version(helm_service, db_session: AsyncSession):
    """mark_helm_version_synced flips is_synced and status to Synced."""
    source = HelmChartSource(
        name="mark-synced-source",
        repo_url="https://charts.example.com/index.yaml",
    )
    db_session.add(source)
    await db_session.commit()

    version = HelmChartVersion(
        source_id=source.id,
        chart_name="nginx",
        version="15.1.0",
        status_flag=4,
        status_text="pending",
        is_synced=False,
    )
    db_session.add(version)
    await db_session.commit()

    await mark_helm_version_synced(db_session, source.id, "nginx", "15.1.0")
    await db_session.commit()

    result = await db_session.execute(
        select(HelmChartVersion).where(HelmChartVersion.id == version.id)
    )
    updated = result.scalar_one()
    assert updated.is_synced is True
    assert updated.status_flag == 0
    assert updated.status_text == "Synced"
    assert updated.last_synced_at is not None


@pytest.mark.asyncio
async def test_mark_helm_version_synced_unknown_version_is_noop(
    helm_service, db_session: AsyncSession
):
    """Unknown version is silently ignored (no crash)."""
    source = HelmChartSource(
        name="mark-noop-source",
        repo_url="https://charts.example.com/index.yaml",
    )
    db_session.add(source)
    await db_session.commit()

    await mark_helm_version_synced(db_session, source.id, "does-not-exist", "0.0.1")


# ─── mirror_chart ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mirror_chart_unknown_version_raises(helm_service, db_session: AsyncSession):
    """mirror_chart requires an indexed version."""
    source = HelmChartSource(
        name="mirror-unknown",
        repo_url="https://charts.example.com/index.yaml",
        gitlab_project_id="12345",
    )
    db_session.add(source)
    await db_session.commit()

    with pytest.raises(NotFoundError, match="not found"):
        await helm_service.mirror_chart(source, "nginx", "1.0.0", db_session)


@pytest.mark.asyncio
async def test_mirror_chart_no_gitlab_project_raises(helm_service, db_session: AsyncSession):
    """mirror_chart requires a GitLab project id."""
    source = HelmChartSource(
        name="mirror-no-project",
        repo_url="https://charts.example.com/index.yaml",
    )
    db_session.add(source)
    await db_session.commit()

    version = HelmChartVersion(
        source_id=source.id,
        chart_name="nginx",
        version="15.1.0",
        status_flag=4,
        status_text="pending",
        is_synced=False,
    )
    db_session.add(version)
    await db_session.commit()

    with pytest.raises(BadRequestError, match="GitLab project"):
        await helm_service.mirror_chart(source, "nginx", "15.1.0", db_session)


@pytest.mark.asyncio
async def test_mirror_chart_triggers_pipeline(helm_service, db_session: AsyncSession):
    """mirror_chart creates a pending/running sync log and triggers the pipeline."""
    source = HelmChartSource(
        name="mirror-ok",
        repo_url="https://charts.example.com/index.yaml",
        gitlab_project_id="12345",
        target_repo_url="oci://harbor.local/bigbug",
    )
    db_session.add(source)
    await db_session.commit()

    version = HelmChartVersion(
        source_id=source.id,
        chart_name="nginx",
        version="15.1.0",
        status_flag=4,
        status_text="pending",
        is_synced=False,
    )
    db_session.add(version)
    await db_session.commit()

    fake_project = MagicMock()
    fake_pipeline = MagicMock()
    fake_pipeline.id = 999
    fake_project.pipelines.create.return_value = fake_pipeline

    fake_gl = MagicMock()
    fake_gl.projects.get.return_value = fake_project

    with (
        patch.object(helm_service, "_get_client", return_value=fake_gl),
        patch("app.services.helm.get_default_gitlab_provider", new=AsyncMock(return_value=None)),
    ):
        log = await helm_service.mirror_chart(
            source, "nginx", "15.1.0", db_session, triggered_by="user:test"
        )
        await db_session.commit()

    assert isinstance(log, HelmSyncLog)
    assert log.chart_name == "nginx"
    assert log.chart_version == "15.1.0"
    assert log.status_flag == 3  # running
    assert log.pipeline_id == "999"
    assert fake_project.pipelines.create.called

    # The version remains un-synced until the webhook reports success.
    result = await db_session.execute(
        select(HelmChartVersion).where(HelmChartVersion.id == version.id)
    )
    assert result.scalar_one().is_synced is False
