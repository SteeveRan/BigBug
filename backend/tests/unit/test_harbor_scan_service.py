"""
@file test_harbor_scan_service.py
@description Unit tests for HarborScanService — scan_image() and
             get_scan_results() with mocked Harbor API.
@dependencies pytest, pytest-asyncio, backend/tests/conftest.py
@relatedFiles ../../app/services/harbor_scan.py, ../../app/models/image_version.py,
               ../../app/models/harbor_instance.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.image_version import ImageVersion
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.services.harbor_scan import (
    HarborScanService,
    _parse_scan_overview,
    _worst_severity,
)

# ──────────────────────────────────────────────────────────────────────
# Helpers: _parse_scan_overview, _worst_severity
# ──────────────────────────────────────────────────────────────────────


class TestParseScanOverview:
    """Unit tests for _parse_scan_overview()"""

    def test_extracts_summary_from_standard_mime(self):
        """Extracts summary from vulnerability report MIME key."""
        artifact = {
            "scan_overview": {
                "application/vnd.security.vulnerability.report; version=1.1": {
                    "summary": {
                        "summary": {
                            "Critical": 2,
                            "High": 5,
                            "Medium": 10,
                            "Low": 3,
                        }
                    }
                }
            }
        }
        result = _parse_scan_overview(artifact)
        assert result == {"Critical": 2, "High": 5, "Medium": 10, "Low": 3}

    def test_no_scan_overview_returns_none(self):
        """Returns None when scan_overview is absent."""
        assert _parse_scan_overview({}) is None

    def test_empty_scan_overview_returns_none(self):
        """Returns None when scan_overview is empty dict."""
        assert _parse_scan_overview({"scan_overview": {}}) is None

    def test_no_vulnerability_mime_returns_none(self):
        """Returns None when no vulnerability MIME key exists."""
        artifact = {
            "scan_overview": {
                "application/vnd.other.report; version=1.0": {"summary": {"summary": {"Total": 0}}}
            }
        }
        result = _parse_scan_overview(artifact)
        # The function iterates scan_overview and looks for "vulnerability" in key
        assert result is None

    def test_summary_in_flat_format(self):
        """Handles flat summary format (without nested summary.summary)."""
        artifact = {
            "scan_overview": {
                "application/vnd.security.vulnerability.report; version=1.1": {
                    "summary": {"Critical": 0, "High": 1, "Medium": 2}
                }
            }
        }
        result = _parse_scan_overview(artifact)
        # The function tries report["summary"]["summary"] first,
        # then falls back to report["summary"] if it's not nested
        # Actually, report["summary"]["summary"] would give None if not present
        # The or report.get("summary", {}) handles the fallback
        # But "Critical" is not a key in summary wrapper, so it returns the summary dict
        assert result == {"Critical": 0, "High": 1, "Medium": 2}


class TestWorstSeverity:
    """Unit tests for _worst_severity()"""

    def test_none_when_all_zero(self):
        assert _worst_severity({"critical": 0, "high": 0, "low": 0}) == "none"

    def test_critical_when_present(self):
        assert _worst_severity({"critical": 1}) == "critical"

    def test_high_over_medium(self):
        assert _worst_severity({"high": 3, "medium": 10}) == "high"

    def test_medium_over_low(self):
        assert _worst_severity({"medium": 1, "low": 5}) == "medium"

    def test_empty_counts(self):
        assert _worst_severity({}) == "none"


# ──────────────────────────────────────────────────────────────────────
# scan_image
# ──────────────────────────────────────────────────────────────────────


class TestHarborScanServiceScanImage:
    """Tests for HarborScanService.scan_image()"""

    async def _create_fixtures(self, db_session: AsyncSession):
        """Create test ImageVersion and Harbor ResourceProvider."""
        version = ImageVersion(
            image_type="gold",
            version_tag="3.0.0",
            arch="amd64",
            registry_url="harbor.example.com",
            sha256_digest="sha256:abc123",
        )
        db_session.add(version)
        await db_session.flush()

        harbor = ResourceProvider(
            domain=ProviderDomain.docker,
            subtype=ProviderSubtype.harbor,
            category=ProviderCategory.system,
            direction=ProviderDirection.internal,
            name="test-harbor",
            label="Test Harbor",
            base_url="https://harbor.example.com",
            verify_ssl=True,
        )
        db_session.add(harbor)
        await db_session.commit()
        await db_session.refresh(version)
        await db_session.refresh(harbor)
        return version, harbor

    @pytest.mark.asyncio
    async def test_scan_image_triggers_harbor_api(self, db_session: AsyncSession):
        """scan_image calls Harbor API with correct parameters."""
        version, harbor = await self._create_fixtures(db_session)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.services.harbor_scan._get_harbor_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            result = await HarborScanService.scan_image(
                db_session,
                version.id,
                harbor.id,
                project_name="myproject",
                repository_name="myrepo",
                artifact_digest="sha256:abc123",
            )

        assert result["status"] == "scanning"

        # Verify the mock was called
        mock_get_client.assert_called_once()
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args[0][0]
        assert "myproject" in call_args
        assert "myrepo" in call_args
        assert "sha256:abc123" in call_args
        assert "/scan" in call_args

        # Verify DB update
        await db_session.refresh(version)
        assert version.status_flag == 3  # STATUS_IN_PROGRESS
        assert version.status_text == "Scanning"

    @pytest.mark.asyncio
    async def test_scan_image_handles_harbor_error(self, db_session: AsyncSession):
        """scan_image handles Harbor API errors gracefully."""
        version, harbor = await self._create_fixtures(db_session)

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.services.harbor_scan._get_harbor_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            with pytest.raises(RuntimeError, match="Harbor scan trigger failed"):
                await HarborScanService.scan_image(
                    db_session,
                    version.id,
                    harbor.id,
                    project_name="myproject",
                    repository_name="myrepo",
                    artifact_digest="sha256:abc123",
                )

    @pytest.mark.asyncio
    async def test_scan_image_version_not_found(self, db_session: AsyncSession):
        """scan_image raises NotFoundError for nonexistent version."""
        with pytest.raises(NotFoundError, match="Image version"):
            await HarborScanService.scan_image(
                db_session,
                image_version_id=99999,
                harbor_instance_id=1,
                project_name="p",
                repository_name="r",
                artifact_digest="sha256:xxx",
            )


# ──────────────────────────────────────────────────────────────────────
# get_scan_results
# ──────────────────────────────────────────────────────────────────────


class TestHarborScanServiceGetResults:
    """Tests for HarborScanService.get_scan_results()"""

    async def _create_fixtures(self, db_session: AsyncSession):
        """Create test ImageVersion and Harbor ResourceProvider."""
        version = ImageVersion(
            image_type="app",
            version_tag="4.0.0",
            arch="amd64",
            registry_url="harbor.example.com",
            sha256_digest="sha256:def456",
        )
        db_session.add(version)
        await db_session.flush()

        harbor = ResourceProvider(
            domain=ProviderDomain.docker,
            subtype=ProviderSubtype.harbor,
            category=ProviderCategory.system,
            direction=ProviderDirection.internal,
            name="test-harbor-results",
            label="Test Harbor Results",
            base_url="https://harbor.example.com",
            verify_ssl=True,
        )
        db_session.add(harbor)
        await db_session.commit()
        await db_session.refresh(version)
        await db_session.refresh(harbor)
        return version, harbor

    @pytest.mark.asyncio
    async def test_get_results_updates_vulnerabilities(self, db_session: AsyncSession):
        """get_scan_results updates image_version.vulnerabilities."""
        version, harbor = await self._create_fixtures(db_session)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "scan_overview": {
                "application/vnd.security.vulnerability.report; version=1.1": {
                    "summary": {
                        "summary": {
                            "Critical": 0,
                            "High": 2,
                            "Medium": 5,
                            "Low": 1,
                            "Negligible": 0,
                        }
                    }
                }
            }
        }

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.services.harbor_scan._get_harbor_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            result = await HarborScanService.get_scan_results(
                db_session,
                version.id,
                harbor.id,
                project_name="myproject",
                repository_name="myrepo",
                artifact_digest="sha256:def456",
            )

        assert result["total"] == 8  # 2+5+1
        assert result["critical"] == 0
        assert result["high"] == 2
        assert result["medium"] == 5
        assert result["low"] == 1
        assert result["severity"] == "high"

        # Verify DB update
        await db_session.refresh(version)
        assert version.vulnerabilities == 8
        assert version.vulnerability_severity == "high"
        assert version.status_flag == 0  # STATUS_OK

    @pytest.mark.asyncio
    async def test_get_results_parses_severity(self, db_session: AsyncSession):
        """get_scan_results correctly parses severity from Harbor response."""
        version, harbor = await self._create_fixtures(db_session)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "scan_overview": {
                "application/vnd.security.vulnerability.report; version=1.1": {
                    "summary": {
                        "summary": {
                            "Critical": 3,
                            "High": 4,
                            "Medium": 0,
                            "Low": 0,
                            "Negligible": 0,
                        }
                    }
                }
            }
        }

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.services.harbor_scan._get_harbor_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            result = await HarborScanService.get_scan_results(
                db_session,
                version.id,
                harbor.id,
                project_name="myproject",
                repository_name="myrepo",
                artifact_digest="sha256:def456",
            )

        assert result["severity"] == "critical"
        assert result["critical"] == 3

    @pytest.mark.asyncio
    async def test_get_results_handles_no_scan_data(self, db_session: AsyncSession):
        """get_scan_results handles missing scan_overview gracefully."""
        version, harbor = await self._create_fixtures(db_session)

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"tags": []}  # No scan_overview

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.services.harbor_scan._get_harbor_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            mock_get_client.return_value = mock_client

            result = await HarborScanService.get_scan_results(
                db_session,
                version.id,
                harbor.id,
                project_name="myproject",
                repository_name="myrepo",
                artifact_digest="sha256:def456",
            )

        assert result["total"] == 0
        assert result["severity"] == "unknown"
        assert "No scan results" in result["message"]

        # Verify DB was updated with failure
        await db_session.refresh(version)
        assert version.status_flag == 1  # STATUS_FAILED
