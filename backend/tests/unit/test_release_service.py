"""
@file test_release_service.py
@description Unit tests for ReleaseService — check_new_releases, fetch_readme,
             fetch_license, check_restricted_license, get_readme, get_license_report.
@dependencies pytest, pytest-asyncio, unittest.mock, sqlalchemy
@relatedFiles ../../app/services/release.py, ../../app/models/source_repository.py,
              ../../app/models/mirror_release_log.py
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source_group import SourceGroup
from app.models.source_provider import ProviderType, SourceProvider
from app.models.source_repository import SourceRepository
from app.services.release import ReleaseService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_source_repo(db: AsyncSession, **overrides) -> SourceRepository:
    """Create a minimal SourceRepository with SourceGroup and SourceProvider."""
    sp = SourceProvider(
        credential_id=1,
        provider_type=ProviderType.github,
        label="test-provider",
    )
    db.add(sp)
    await db.flush()

    sg = SourceGroup(
        external_id="testorg",
        name="Test Org",
        full_path="testorg",
    )
    db.add(sg)
    await db.flush()

    defaults = {
        "source_provider_id": sp.id,
        "source_group_id": sg.id,
        "external_id": "12345",
        "name": "test-repo",
        "full_name": "testorg/test-repo",
        "latest_release_tag": "v1.0.0",
        "latest_release_name": "First Release",
        "latest_release_date": datetime(2025, 1, 1, tzinfo=UTC),
        "latest_release_url": "https://github.com/testorg/test-repo/releases/v1.0.0",
    }
    defaults.update(overrides)
    sr = SourceRepository(**defaults)
    db.add(sr)
    await db.commit()
    await db.refresh(sr)
    return sr


def _make_github_provider_mock():
    """Build a mock GitHubSourceProvider."""
    mock_gh_provider = MagicMock()
    mock_gh_provider._get_client = MagicMock()
    return mock_gh_provider


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCheckNewReleases:
    """Tests for ReleaseService.check_new_releases()"""

    @pytest.mark.asyncio
    async def test_check_new_releases_new_found(self, db_session: AsyncSession):
        """check_new_releases detects new tag and creates MirrorReleaseLog."""
        sr = await _seed_source_repo(db_session, latest_release_tag="v1.0.0")
        gh_provider = _make_github_provider_mock()

        # Mock the GitHub release response
        mock_release = MagicMock()
        mock_release.tag_name = "v2.0.0"
        mock_release.title = "Second Release"
        mock_release.body = "Release notes v2"
        mock_release.html_url = "https://github.com/testorg/test-repo/releases/v2.0.0"
        mock_release.published_at = datetime(2025, 6, 1, tzinfo=UTC)
        mock_release.prerelease = False

        mock_releases = MagicMock()
        mock_releases.totalCount = 3
        mock_releases.__getitem__.return_value = mock_release

        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = mock_releases

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        gh_provider._get_client.return_value = mock_gh

        with patch("app.services.release.AuditService.log_event", new_callable=AsyncMock):
            release_log = await ReleaseService.check_new_releases(db_session, sr, gh_provider)

        assert release_log is not None
        assert release_log.tag == "v2.0.0"
        assert release_log.name == "Second Release"

        # SourceRepository should be updated
        await db_session.refresh(sr)
        assert sr.latest_release_tag == "v2.0.0"
        assert sr.latest_release_name == "Second Release"

    @pytest.mark.asyncio
    async def test_check_new_releases_no_change(self, db_session: AsyncSession):
        """check_new_releases returns None when tag is unchanged."""
        sr = await _seed_source_repo(
            db_session,
            latest_release_tag="v1.0.0",
            latest_release_name="First Release",
        )
        gh_provider = _make_github_provider_mock()

        mock_release = MagicMock()
        mock_release.tag_name = "v1.0.0"  # Same tag
        mock_release.title = "First Release"

        mock_releases = MagicMock()
        mock_releases.totalCount = 3
        mock_releases.__getitem__.return_value = mock_release

        mock_repo = MagicMock()
        mock_repo.get_releases.return_value = mock_releases

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        gh_provider._get_client.return_value = mock_gh

        with patch("app.services.release.AuditService.log_event", new_callable=AsyncMock):
            result = await ReleaseService.check_new_releases(db_session, sr, gh_provider)

        assert result is None


class TestFetchReadme:
    """Tests for ReleaseService.fetch_readme_from_source()"""

    @pytest.mark.asyncio
    async def test_fetch_readme(self, db_session: AsyncSession):
        """fetch_readme_from_source decodes base64 and caches content."""

        sr = await _seed_source_repo(db_session)
        gh_provider = _make_github_provider_mock()

        readme_content = "# Test README\nThis is a test."

        mock_readme = MagicMock()
        mock_readme.decoded_content = readme_content.encode("utf-8")

        mock_repo = MagicMock()
        mock_repo.get_readme.return_value = mock_readme

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        gh_provider._get_client.return_value = mock_gh

        content = await ReleaseService.fetch_readme_from_source(db_session, sr, gh_provider)

        assert "# Test README" in content
        await db_session.refresh(sr)
        assert sr.readme_html is not None
        assert "# Test README" in sr.readme_html
        assert sr.readme_fetched_at is not None


class TestFetchLicense:
    """Tests for ReleaseService.fetch_license_from_source()"""

    @pytest.mark.asyncio
    async def test_fetch_license(self, db_session: AsyncSession):
        """fetch_license_from_source caches SPDX and returns dict."""
        sr = await _seed_source_repo(db_session)
        gh_provider = _make_github_provider_mock()

        mock_license_info = MagicMock()
        mock_license_info.license = MagicMock()
        mock_license_info.license.spdx_id = "MIT"
        mock_license_info.license.name = "MIT License"

        mock_repo = MagicMock()
        mock_repo.get_license.return_value = mock_license_info

        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        gh_provider._get_client.return_value = mock_gh

        result = await ReleaseService.fetch_license_from_source(db_session, sr, gh_provider)

        assert result["spdx"] == "MIT"
        assert result["name"] == "MIT License"
        assert result["is_restricted"] is False

        await db_session.refresh(sr)
        assert sr.license_spdx == "MIT"


class TestCheckRestrictedLicense:
    """Tests for ReleaseService.check_restricted_license()"""

    @pytest.mark.asyncio
    async def test_check_restricted_license_true(self):
        """check_restricted_license returns True for restricted license."""
        with patch.dict("os.environ", {"RESTRICTED_LICENSES": "GPL-3.0,AGPL-3.0"}):
            assert ReleaseService.check_restricted_license("GPL-3.0") is True
            assert ReleaseService.check_restricted_license("AGPL-3.0") is True

    @pytest.mark.asyncio
    async def test_check_restricted_license_false(self):
        """check_restricted_license returns False for non-restricted license."""
        with patch.dict("os.environ", {"RESTRICTED_LICENSES": "GPL-3.0,AGPL-3.0"}):
            assert ReleaseService.check_restricted_license("MIT") is False
            assert ReleaseService.check_restricted_license("Apache-2.0") is False


class TestGetReadme:
    """Tests for ReleaseService.get_readme()"""

    @pytest.mark.asyncio
    async def test_get_readme_cached(self, db_session: AsyncSession):
        """get_readme returns cached content when readme_html is set."""
        sr = await _seed_source_repo(
            db_session,
            readme_html="<h1>Test</h1>",
            readme_fetched_at=datetime(2025, 1, 1, tzinfo=UTC),
        )

        result = await ReleaseService.get_readme(db_session, sr.id)

        assert result is not None
        assert result["html"] == "<h1>Test</h1>"
        assert result["fetched_at"] is not None

    @pytest.mark.asyncio
    async def test_get_readme_not_fetched(self, db_session: AsyncSession):
        """get_readme returns None when readme_html is NULL."""
        sr = await _seed_source_repo(db_session, readme_html=None)

        result = await ReleaseService.get_readme(db_session, sr.id)
        assert result is None


class TestGetLicenseReport:
    """Tests for ReleaseService.get_license_report()"""

    @pytest.mark.asyncio
    async def test_get_license_report(self, db_session: AsyncSession):
        """get_license_report aggregates licenses across repositories."""
        await _seed_source_repo(
            db_session,
            external_id="1",
            name="repo1",
            full_name="testorg/repo1",
            license_spdx="MIT",
            license_name="MIT License",
            web_url="https://github.com/testorg/repo1",
        )
        await _seed_source_repo(
            db_session,
            external_id="2",
            name="repo2",
            full_name="testorg/repo2",
            license_spdx="MIT",
            license_name="MIT License",
            web_url="https://github.com/testorg/repo2",
        )
        await _seed_source_repo(
            db_session,
            external_id="3",
            name="repo3",
            full_name="testorg/repo3",
            license_spdx="Apache-2.0",
            license_name="Apache License 2.0",
            web_url="https://github.com/testorg/repo3",
        )

        with patch.dict("os.environ", {"RESTRICTED_LICENSES": ""}):
            report = await ReleaseService.get_license_report(db_session)

        assert len(report) == 2  # Two distinct licenses

        # Sort by name
        report.sort(key=lambda x: x.get("name", ""))

        # Apache should be first alphabetically
        apache_entry = report[0]
        assert apache_entry["spdx"] == "Apache-2.0"
        assert apache_entry["count"] == 1
        assert len(apache_entry["repositories"]) == 1

        mit_entry = report[1]
        assert mit_entry["spdx"] == "MIT"
        assert mit_entry["count"] == 2
        assert len(mit_entry["repositories"]) == 2
