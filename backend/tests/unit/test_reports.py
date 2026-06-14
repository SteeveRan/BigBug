"""
@file test_reports.py
@description Unit tests for ReportsService — duplicates, storage, status, syncs reports,
             bulk operations, and CSV/JSON export.
@dependencies pytest, pytest-asyncio, unittest.mock
@relatedFiles ../../app/services/reports.py, ../../app/api/reports.py, ../../app/schemas/reports.py
"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential import Credential, CredentialType
from app.models.gitlab_instance import GitlabInstance
from app.models.mirror import Mirror
from app.models.mirror_log import MirrorLog, MirrorLogType
from app.models.pipeline import Pipeline as PipelineModel
from app.models.source_group import SourceGroup
from app.models.source_provider import ProviderType, SourceProvider
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.schemas.reports import (
    BulkReassignSyncGroupRequest,
    DuplicatesReport,
    StatusReport,
    SyncsReport,
)
from app.services.reports import ReportsService, _storage_cache

# ═══════════════════════════════════════════════════════════════════════════
# Test helpers
# ═══════════════════════════════════════════════════════════════════════════


_seed_counter: int = 0


async def _seed_mirror_chain(
    db: AsyncSession,
    *,
    source_name: str = "test-repo",
    source_full_name: str = "testorg/test-repo",
    source_url: str = "https://github.com/testorg/test-repo.git",
    target_namespace: str = "testns",
    target_project_name: str = "test-repo",
    target_project_id: str = "42",
    status_flag: int = 0,
    status_text: str = "OK",
    sg_name: str = "test-sync-group",
    gl_instance_name: str = "test-gitlab",
    gl_url: str = "https://gitlab.example.com",
) -> Mirror:
    """Create a full mirror chain and return the Mirror."""
    global _seed_counter
    _seed_counter += 1

    cred = Credential(
        name=f"test-cred-{_seed_counter}",
        credential_type=CredentialType.github_token,
        provider="github",
        encrypted_secret="gAAAAAB...",
        status_flag=0,
    )
    db.add(cred)
    await db.flush()

    sp = SourceProvider(
        credential_id=cred.id,
        provider_type=ProviderType.github,
        label=f"test-provider-{_seed_counter}",
    )
    db.add(sp)
    await db.flush()

    sg = SourceGroup(
        external_id=f"testorg-{_seed_counter}",
        name=f"Test Org {_seed_counter}",
        full_path=f"testorg-{_seed_counter}",
    )
    db.add(sg)
    await db.flush()

    sr = SourceRepository(
        source_group_id=sg.id,
        external_id=f"{_seed_counter}",
        name=source_name,
        full_name=source_full_name,
        clone_url_https=source_url,
    )
    db.add(sr)
    await db.flush()

    # Reuse existing GitlabInstance by name to avoid UNIQUE constraint on url
    existing_instance = (
        await db.execute(select(GitlabInstance).where(GitlabInstance.name == gl_instance_name))
    ).scalar_one_or_none()
    if existing_instance is not None:
        instance = existing_instance
    else:
        instance = GitlabInstance(
            url=gl_url,
            token="gAAAAAB...",
            verify_ssl=True,
            name=gl_instance_name,
        )
        db.add(instance)
        await db.flush()

    # Reuse existing Pipeline by name
    existing_pipeline = (
        await db.execute(select(PipelineModel).where(PipelineModel.name == "test-pipeline"))
    ).scalar_one_or_none()
    if existing_pipeline is not None:
        pipeline = existing_pipeline
    else:
        pipeline = PipelineModel(
            name="test-pipeline",
            gitlab_instance_id=instance.id,
            ref="main",
        )
        db.add(pipeline)
        await db.flush()

    # Reuse existing SyncGroup by name to avoid UNIQUE constraint on name and is_default
    existing_sg = (
        await db.execute(select(SyncGroup).where(SyncGroup.name == sg_name))
    ).scalar_one_or_none()
    if existing_sg is not None:
        sync_group = existing_sg
    else:
        sync_group = SyncGroup(
            name=sg_name,
            description="Test group",
            is_default=False,
            pipeline_id=pipeline.id,
        )
        db.add(sync_group)
        await db.flush()

    mirror = Mirror(
        source_repository_id=sr.id,
        sync_group_id=sync_group.id,
        target_namespace=target_namespace,
        target_project_name=target_project_name,
        target_project_id=target_project_id,
        status_flag=status_flag,
        status_text=status_text,
    )
    db.add(mirror)
    await db.commit()
    await db.refresh(mirror)
    return mirror


def _clear_storage_cache():
    """Reset the global storage cache between tests."""
    _storage_cache["items"] = []
    _storage_cache["by_gitlab_instance"] = []
    _storage_cache["by_sync_group"] = []
    _storage_cache["grand_total"] = None
    _storage_cache["collected_at"] = None
    _storage_cache["collection_status"] = "idle"


# ═══════════════════════════════════════════════════════════════════════════
# 1. Duplicates Report Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDuplicatesReport:
    """Tests for ReportsService.report_duplicates()."""

    @pytest.mark.asyncio
    async def test_no_duplicates_when_single_mirror(self, db_session: AsyncSession):
        """report_duplicates returns empty groups when mirrors have unique source URLs."""
        _clear_storage_cache()
        await _seed_mirror_chain(
            db_session,
            source_url="https://github.com/testorg/repo-a.git",
            target_project_name="repo-a",
        )
        await _seed_mirror_chain(
            db_session,
            source_url="https://github.com/testorg/repo-b.git",
            target_project_name="repo-b",
            sg_name="other-group",
            gl_instance_name="other-gitlab",
            gl_url="https://gitlab2.example.com",
        )

        report = await ReportsService.report_duplicates(db_session)

        assert isinstance(report, DuplicatesReport)
        assert report.total_groups == 0
        assert report.total_mirrors == 0
        assert report.groups == []

    @pytest.mark.asyncio
    async def test_finds_duplicate_group(self, db_session: AsyncSession):
        """report_duplicates finds mirrors sharing the same source_url."""
        _clear_storage_cache()
        url = "https://github.com/testorg/repo-dup.git"
        await _seed_mirror_chain(
            db_session,
            source_url=url,
            target_project_name="repo-dup-inst1",
            sg_name="group-a",
        )
        await _seed_mirror_chain(
            db_session,
            source_url=url,
            target_project_name="repo-dup-inst2",
            sg_name="group-b",
            gl_instance_name="other-gitlab",
            gl_url="https://gitlab2.example.com",
        )

        report = await ReportsService.report_duplicates(db_session)

        assert report.total_groups == 1
        assert report.total_mirrors == 2
        assert len(report.groups) == 1
        assert report.groups[0].mirror_count == 2
        assert report.groups[0].source_url == url
        assert "1 групп" in report.warning or "1 group" in report.warning.lower()

    @pytest.mark.asyncio
    async def test_ignores_soft_deleted_mirrors(self, db_session: AsyncSession):
        """report_duplicates excludes mirrors with is_deleted=True."""
        _clear_storage_cache()
        url = "https://github.com/testorg/repo-dup2.git"
        await _seed_mirror_chain(
            db_session,
            source_url=url,
            target_project_name="repo-active",
            sg_name="group-a",
        )
        mirror_b = await _seed_mirror_chain(
            db_session,
            source_url=url,
            target_project_name="repo-deleted",
            sg_name="group-b",
        )
        # Soft-delete mirror_b
        mirror_b.is_deleted = True
        mirror_b.deleted_at = datetime.now(UTC)
        await db_session.commit()

        report = await ReportsService.report_duplicates(db_session)

        # Only the active mirror remains → no duplicate group
        assert report.total_groups == 0


# ═══════════════════════════════════════════════════════════════════════════
# 2. Storage Report Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestStorageReport:
    """Tests for ReportsService.report_storage() and refresh_storage()."""

    @pytest.mark.asyncio
    async def test_storage_uses_cache_on_second_call(self, db_session: AsyncSession):
        """report_storage collects from API once, then serves from cache."""
        _clear_storage_cache()
        await _seed_mirror_chain(db_session)

        with patch(
            "app.services.reports.GitLabService._get_client",
            autospec=True,
        ) as mock_client:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_stats = MagicMock()
            mock_stats.repository_size = 1048576  # 1 MB
            mock_stats.lfs_objects_size = 0
            mock_stats.build_artifacts_size = 0
            mock_stats.packages_size = 0
            mock_stats.wiki_size = 0
            mock_stats.snippets_size = 0
            mock_project.statistics = mock_stats
            mock_gl.projects.get.return_value = mock_project
            mock_client.return_value = mock_gl

            report1 = await ReportsService.report_storage(db_session)
            report2 = await ReportsService.report_storage(db_session)

        assert report1.collection_status == "complete"
        assert report1.is_stale is False
        assert len(report1.items) == 1
        assert report1.items[0].repo_size_bytes == 1048576
        assert report1.items[0].accessible is True
        # Second call should use cache — client only called once
        mock_client.assert_called_once()
        assert report2.collection_status == "complete"
        assert report2.is_stale is False

    @pytest.mark.asyncio
    async def test_storage_force_refresh_bypasses_cache(self, db_session: AsyncSession):
        """refresh_storage forces a fresh collection regardless of cache."""
        _clear_storage_cache()
        await _seed_mirror_chain(db_session)

        call_count = 0

        class CountingGL:
            def __init__(self, *args, **kwargs):
                pass

            @property
            def projects(self):
                return self

            def get(self, project_id=None, statistics=False):
                nonlocal call_count
                call_count += 1
                mock_project = MagicMock()
                mock_stats = MagicMock()
                mock_stats.repository_size = 524288
                mock_stats.lfs_objects_size = 0
                mock_stats.build_artifacts_size = 0
                mock_stats.packages_size = 0
                mock_stats.wiki_size = 0
                mock_stats.snippets_size = 0
                mock_project.statistics = mock_stats
                return mock_project

        with patch(
            "app.services.reports.GitLabService._get_client",
            return_value=CountingGL(),
        ):
            report1 = await ReportsService.report_storage(db_session)
            report2 = await ReportsService.refresh_storage(db_session)

        assert report1.collection_status == "complete"
        assert report2.collection_status == "complete"
        # Force refresh should have triggered another API call
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_storage_handles_gitlab_api_error(self, db_session: AsyncSession):
        """report_storage marks items with error when GitLab API fails."""
        _clear_storage_cache()
        await _seed_mirror_chain(db_session)

        with patch(
            "app.services.reports.GitLabService._get_client",
            autospec=True,
        ) as mock_client:
            mock_gl = MagicMock()
            mock_gl.projects.get.side_effect = Exception("GitLab unavailable")
            mock_client.return_value = mock_gl

            report = await ReportsService.report_storage(db_session)

        assert len(report.items) == 1
        assert report.items[0].accessible is False
        assert report.items[0].error is not None
        assert "GitLab unavailable" in report.items[0].error
        assert report.items[0].repo_size_bytes is None


# ═══════════════════════════════════════════════════════════════════════════
# 3. Status Report Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestStatusReport:
    """Tests for ReportsService.report_status()."""

    @pytest.mark.asyncio
    async def test_status_counts_empty_db(self, db_session: AsyncSession):
        """report_status returns zero counts and empty lists on empty DB."""
        _clear_storage_cache()
        report = await ReportsService.report_status(db_session)

        assert isinstance(report, StatusReport)
        assert report.total_mirrors == 0
        total_from_counts = sum(c.count for c in report.status_counts)
        assert total_from_counts == 0

    @pytest.mark.asyncio
    async def test_status_counts_by_flag(self, db_session: AsyncSession):
        """report_status correctly groups mirrors by status_flag."""
        _clear_storage_cache()
        await _seed_mirror_chain(db_session, status_flag=0, target_project_name="ok-mirror")
        await _seed_mirror_chain(
            db_session,
            status_flag=1,
            status_text="Failed",
            target_project_name="fail-mirror",
        )
        await _seed_mirror_chain(
            db_session,
            status_flag=3,
            status_text="In Progress",
            target_project_name="wip-mirror",
        )

        report = await ReportsService.report_status(db_session)

        assert report.total_mirrors == 3
        # Check status counts
        count_map = {c.status_flag: c.count for c in report.status_counts}
        assert count_map.get(0) == 1
        assert count_map.get(1) == 1
        assert count_map.get(2) == 0
        assert count_map.get(3) == 1
        assert count_map.get(4) == 0

    @pytest.mark.asyncio
    async def test_status_drilldown_lists(self, db_session: AsyncSession):
        """report_status returns per-status drill-down lists."""
        _clear_storage_cache()
        await _seed_mirror_chain(
            db_session,
            status_flag=0,
            target_project_name="ok-mirror",
        )
        await _seed_mirror_chain(
            db_session,
            status_flag=1,
            status_text="GitLab API error",
            target_project_name="fail-mirror",
        )

        report = await ReportsService.report_status(db_session)

        assert len(report.ok_mirrors) == 1
        assert report.ok_mirrors[0].status_flag == 0
        assert len(report.failed_mirrors) == 1
        assert report.failed_mirrors[0].status_text == "GitLab API error"
        assert report.failed_mirrors[0].mirror_id is not None


# ═══════════════════════════════════════════════════════════════════════════
# 4. Syncs Report Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSyncsReport:
    """Tests for ReportsService.report_syncs()."""

    async def _add_sync_log(
        self,
        db: AsyncSession,
        mirror: Mirror,
        status_flag: int,
        days_ago: int,
    ) -> None:
        """Add a MirrorLog of type sync with specified status and age."""
        log = MirrorLog(
            mirror_id=mirror.id,
            log_type=MirrorLogType.sync,
            status_flag=status_flag,
            status_text="test",
            created_at=datetime.now(UTC) - timedelta(days=days_ago),
        )
        db.add(log)
        await db.commit()

    @pytest.mark.asyncio
    async def test_syncs_default_30_days(self, db_session: AsyncSession):
        """report_syncs returns data for last 30 days by default."""
        _clear_storage_cache()
        mirror = await _seed_mirror_chain(db_session)

        # Add sync logs at various days
        await self._add_sync_log(db_session, mirror, 0, days_ago=1)
        await self._add_sync_log(db_session, mirror, 0, days_ago=3)
        await self._add_sync_log(db_session, mirror, 1, days_ago=5)

        report = await ReportsService.report_syncs(db_session)

        assert isinstance(report, SyncsReport)
        # The default range is 30 days
        total_syncs = sum(d.total for d in report.daily)
        total_success = sum(d.successful for d in report.daily)
        total_failed = sum(d.failed for d in report.daily)
        assert total_syncs == 3
        assert total_success == 2
        assert total_failed == 1

    @pytest.mark.asyncio
    async def test_syncs_custom_period(self, db_session: AsyncSession):
        """report_syncs respects custom period_start and period_end."""
        _clear_storage_cache()
        mirror = await _seed_mirror_chain(db_session)

        today = date.today()
        # Add a log for today
        await self._add_sync_log(db_session, mirror, 0, days_ago=0)
        # Add a log 10 days ago (outside 7-day window)
        await self._add_sync_log(db_session, mirror, 0, days_ago=10)

        report = await ReportsService.report_syncs(
            db_session,
            period_start=today - timedelta(days=7),
            period_end=today,
        )

        total_syncs = sum(d.total for d in report.daily)
        # Only the today log should be counted
        assert total_syncs == 1

    @pytest.mark.asyncio
    async def test_syncs_top_lists(self, db_session: AsyncSession):
        """report_syncs returns top-10 mirrors by sync count and error count."""
        _clear_storage_cache()
        mirror_a = await _seed_mirror_chain(
            db_session,
            target_project_name="repo-a",
            source_url="https://github.com/testorg/repo-a.git",
        )
        mirror_b = await _seed_mirror_chain(
            db_session,
            target_project_name="repo-b",
            source_url="https://github.com/testorg/repo-b.git",
        )

        # Mirror A: 5 successful syncs
        for i in range(5):
            await self._add_sync_log(db_session, mirror_a, 0, days_ago=i)
        # Mirror B: 2 failed syncs
        await self._add_sync_log(db_session, mirror_b, 1, days_ago=1)
        await self._add_sync_log(db_session, mirror_b, 1, days_ago=2)

        report = await ReportsService.report_syncs(db_session)

        # Top by syncs: mirror_a should be #1
        assert len(report.top_by_syncs) >= 1
        assert report.top_by_syncs[0].mirror_id == mirror_a.id
        assert report.top_by_syncs[0].count == 5

        # Top by errors: mirror_b should be #1
        assert len(report.top_by_errors) >= 1
        assert report.top_by_errors[0].mirror_id == mirror_b.id
        assert report.top_by_errors[0].count == 2


# ═══════════════════════════════════════════════════════════════════════════
# 5. Bulk Operations Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestBulkOperations:
    """Tests for bulk_reassign_sync_group() and bulk_apply_pipeline()."""

    @pytest.mark.asyncio
    async def test_bulk_reassign_sync_group_success(self, db_session: AsyncSession):
        """bulk_reassign_sync_group moves mirrors to a new SyncGroup."""
        _clear_storage_cache()
        mirror_a = await _seed_mirror_chain(
            db_session,
            target_project_name="repo-a",
            sg_name="group-source",
        )
        mirror_b = await _seed_mirror_chain(
            db_session,
            target_project_name="repo-b",
            sg_name="group-source",
        )
        # Create a target SyncGroup
        target_sg = SyncGroup(
            name="group-target",
            description="Target group",
        )
        db_session.add(target_sg)
        await db_session.commit()
        await db_session.refresh(target_sg)

        from app.schemas.reports import BulkReassignSyncGroupRequest

        data = BulkReassignSyncGroupRequest(
            mirror_ids=[mirror_a.id, mirror_b.id],
            sync_group_id=target_sg.id,
        )
        response = await ReportsService.bulk_reassign_sync_group(db_session, data)

        assert response.operation == "reassign-sync-group"
        assert response.total == 2
        assert response.succeeded == 2
        assert response.failed == 0

        # Verify mirrors were actually reassigned
        await db_session.refresh(mirror_a)
        await db_session.refresh(mirror_b)
        assert mirror_a.sync_group_id == target_sg.id
        assert mirror_b.sync_group_id == target_sg.id

    @pytest.mark.asyncio
    async def test_bulk_operation_mirror_not_found(self, db_session: AsyncSession):
        """bulk operation returns failure for non-existent mirrors."""
        _clear_storage_cache()
        # Create one valid mirror
        mirror = await _seed_mirror_chain(db_session)

        target_sg = SyncGroup(name="group-target")
        db_session.add(target_sg)
        await db_session.commit()
        await db_session.refresh(target_sg)

        data = BulkReassignSyncGroupRequest(
            mirror_ids=[mirror.id, 99999],
            sync_group_id=target_sg.id,
        )
        response = await ReportsService.bulk_reassign_sync_group(db_session, data)

        assert response.total == 2
        assert response.succeeded == 1
        assert response.failed == 1
        assert any(r.mirror_id == 99999 and not r.success for r in response.results)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Export Tests (CSV/JSON)
# ═══════════════════════════════════════════════════════════════════════════


class TestExport:
    """Tests for CSV and JSON export serialization."""

    @pytest.mark.asyncio
    async def test_export_duplicates_csv(self, db_session: AsyncSession):
        """Duplicates CSV export produces valid CSV with expected columns."""
        _clear_storage_cache()
        url = "https://github.com/testorg/dup-export.git"
        await _seed_mirror_chain(
            db_session,
            source_url=url,
            target_project_name="dup-inst1",
        )
        await _seed_mirror_chain(
            db_session,
            source_url=url,
            target_project_name="dup-inst2",
        )

        from app.api.reports import _serialize_duplicates_csv

        report = await ReportsService.report_duplicates(db_session)
        csv_data = _serialize_duplicates_csv(report)

        lines = csv_data.strip().split("\r\n" if "\r\n" in csv_data else "\n")
        assert len(lines) >= 2  # header + at least 1 data row
        assert "group_source_url" in lines[0]
        assert "dup-export" in csv_data

    @pytest.mark.asyncio
    async def test_export_storage_json(self, db_session: AsyncSession):
        """Storage JSON export produces valid JSON structure."""
        _clear_storage_cache()
        await _seed_mirror_chain(db_session)

        with patch(
            "app.services.reports.GitLabService._get_client",
            autospec=True,
        ) as mock_client:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_stats = MagicMock()
            mock_stats.repository_size = 102400
            mock_stats.lfs_objects_size = 0
            mock_stats.build_artifacts_size = 0
            mock_stats.packages_size = 0
            mock_stats.wiki_size = 0
            mock_stats.snippets_size = 0
            mock_project.statistics = mock_stats
            mock_gl.projects.get.return_value = mock_project
            mock_client.return_value = mock_gl

            report = await ReportsService.report_storage(db_session)

        json_str = report.model_dump_json(indent=2)
        import json

        data = json.loads(json_str)
        assert "items" in data
        assert "grand_total" in data
        assert len(data["items"]) == 1
        assert data["items"][0]["accessible"] is True
        assert data["items"][0]["repo_size_bytes"] == 102400
