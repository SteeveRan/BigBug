"""
@file test_orphaned.py
@description Unit tests for OrphanedMirrorService — discovery of GitLab
             projects not tracked by BigBug mirrors.
@dependencies pytest, pytest-asyncio, unittest.mock
@relatedFiles ../../app/services/orphaned.py
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mirror import Mirror
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.models.source_group import SourceGroup
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.services.orphaned import OrphanedMirrorService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_gitlab_provider(db: AsyncSession) -> ResourceProvider:
    """Create a system/internal gitlab ResourceProvider for orphaned scanning."""
    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.gitlab,
        category=ProviderCategory.system,
        direction=ProviderDirection.internal,
        name="test-gitlab-provider",
        label="Test GitLab",
        base_url="https://gitlab.example.com",
        verify_ssl=True,
        is_active=True,
    )
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


async def _seed_mirror(db: AsyncSession, target_project_id: str = "42") -> Mirror:
    """Create a minimal mirror with target_project_id for known-ids check."""
    sg = SourceGroup(
        external_id="testorg",
        name="Test Org",
        full_path="testorg",
    )
    db.add(sg)
    await db.flush()

    sr = SourceRepository(
        source_group_id=sg.id,
        external_id="12345",
        name="test-repo",
        full_name="testorg/test-repo",
        clone_url_https="https://github.com/testorg/test-repo.git",
    )
    db.add(sr)
    await db.flush()

    sync_group = SyncGroup(
        name="test-sync-group",
        is_default=False,
    )
    db.add(sync_group)
    await db.flush()

    mirror = Mirror(
        source_repository_id=sr.id,
        sync_group_id=sync_group.id,
        target_namespace="testns",
        target_project_name="test-repo",
        target_project_id=target_project_id,
        status_flag=0,
        status_text="OK",
    )
    db.add(mirror)
    await db.commit()
    await db.refresh(mirror)
    return mirror


# ---------------------------------------------------------------------------
# Tests: find_orphaned
# ---------------------------------------------------------------------------


class TestFindOrphaned:
    """Tests for OrphanedMirrorService.find_orphaned()."""

    @pytest.mark.asyncio
    async def test_no_providers_raises(self, db_session: AsyncSession):
        """Raises DomainError when no GitLab providers exist."""
        from app.core.exceptions import DomainError

        with pytest.raises(DomainError, match="No GitLab providers"):
            await OrphanedMirrorService.find_orphaned(db_session)

    @pytest.mark.asyncio
    async def test_empty_gitlab_returns_empty(self, db_session: AsyncSession):
        """Returns empty report when GitLab has no projects."""
        await _seed_gitlab_provider(db_session)

        with (
            patch("app.services.orphaned.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.orphaned._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class,
        ):
            mock_gl = MagicMock()
            mock_gl.projects.list.return_value = []
            mock_gl_class.return_value = mock_gl

            report = await OrphanedMirrorService.find_orphaned(db_session)

        assert report.count == 0
        assert report.items == []

    @pytest.mark.asyncio
    async def test_all_known_returns_empty(self, db_session: AsyncSession):
        """Returns empty report when all GitLab projects are tracked."""
        await _seed_gitlab_provider(db_session)
        await _seed_mirror(db_session, target_project_id="42")

        with (
            patch("app.services.orphaned.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.orphaned._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class,
        ):
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_project.id = 42
            mock_project.path_with_namespace = "testns/test-repo"
            mock_project.web_url = "https://gitlab.example.com/testns/test-repo"
            mock_project.created_at = "2025-01-01T00:00:00Z"
            mock_gl.projects.list.return_value = [mock_project]
            mock_gl_class.return_value = mock_gl

            report = await OrphanedMirrorService.find_orphaned(db_session)

        assert report.count == 0

    @pytest.mark.asyncio
    async def test_finds_orphaned_projects(self, db_session: AsyncSession):
        """Reports GitLab projects not tracked by BigBug."""
        await _seed_gitlab_provider(db_session)
        await _seed_mirror(db_session, target_project_id="42")

        with (
            patch("app.services.orphaned.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.orphaned._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class,
        ):
            mock_gl = MagicMock()

            # Known project (id=42)
            known_project = MagicMock()
            known_project.id = 42
            known_project.path_with_namespace = "testns/test-repo"
            known_project.web_url = "https://gitlab.example.com/testns/test-repo"
            known_project.created_at = "2025-01-01T00:00:00Z"

            # Orphaned project (id=99)
            orphaned_project = MagicMock()
            orphaned_project.id = 99
            orphaned_project.path_with_namespace = "orphaned/project"
            orphaned_project.web_url = "https://gitlab.example.com/orphaned/project"
            orphaned_project.created_at = "2025-02-01T00:00:00Z"

            mock_gl.projects.list.return_value = [known_project, orphaned_project]
            mock_gl_class.return_value = mock_gl

            report = await OrphanedMirrorService.find_orphaned(db_session)

        assert report.count == 1
        assert report.items[0].gitlab_project_id == 99
        assert report.items[0].target_path == "orphaned/project"
        assert report.items[0].reason == "No matching BigBug mirror record"

    @pytest.mark.asyncio
    async def test_filters_by_provider_id(self, db_session: AsyncSession):
        """find_orphaned scoped to a specific provider returns only from it."""
        provider = await _seed_gitlab_provider(db_session)

        with (
            patch("app.services.orphaned.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.orphaned._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class,
        ):
            mock_gl = MagicMock()
            orphaned_project = MagicMock()
            orphaned_project.id = 55
            orphaned_project.path_with_namespace = "extra/project"
            orphaned_project.web_url = "https://gitlab.example.com/extra/project"
            orphaned_project.created_at = "2025-03-01T00:00:00Z"
            mock_gl.projects.list.return_value = [orphaned_project]
            mock_gl_class.return_value = mock_gl

            report = await OrphanedMirrorService.find_orphaned_for_instance(db_session, provider.id)

        assert report.count == 1
        assert report.provider_id == provider.id

    @pytest.mark.asyncio
    async def test_api_error_handled_gracefully(self, db_session: AsyncSession):
        """GitLab API errors are caught and return empty report."""
        await _seed_gitlab_provider(db_session)

        with (
            patch("app.services.orphaned.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.orphaned._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class,
        ):
            mock_gl = MagicMock()
            mock_gl.projects.list.side_effect = RuntimeError("Connection refused")
            mock_gl_class.return_value = mock_gl

            report = await OrphanedMirrorService.find_orphaned(db_session)

        # Should return empty report without raising
        assert report.count == 0

    @pytest.mark.asyncio
    async def test_orphaned_report_dataclass(self, db_session: AsyncSession):
        """OrphanedReport.count property works correctly."""
        await _seed_gitlab_provider(db_session)

        with (
            patch("app.services.orphaned.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.orphaned._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class,
        ):
            mock_gl = MagicMock()
            proj1 = MagicMock()
            proj1.id = 100
            proj1.path_with_namespace = "a/b"
            proj1.web_url = "https://x"
            proj1.created_at = "2025-01-01T00:00:00Z"
            proj2 = MagicMock()
            proj2.id = 200
            proj2.path_with_namespace = "c/d"
            proj2.web_url = "https://y"
            proj2.created_at = "2025-02-01T00:00:00Z"
            mock_gl.projects.list.return_value = [proj1, proj2]
            mock_gl_class.return_value = mock_gl

            report = await OrphanedMirrorService.find_orphaned(db_session)

        assert report.count == 2
        assert report.scanned_at is not None
        assert report.provider_url == "https://gitlab.example.com"
