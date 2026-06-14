"""
@file test_health_check.py
@description Unit tests for HealthCheckService — system, sync group, and mirror
             health checks. Also tests the HealthCheckReport.overall aggregation.
@dependencies pytest, pytest-asyncio, unittest.mock
@relatedFiles ../../app/services/health_check.py
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential import Credential, CredentialType
from app.models.gitlab_instance import GitlabInstance
from app.models.mirror import Mirror
from app.models.pipeline import Pipeline
from app.models.source_group import SourceGroup
from app.models.source_provider import ProviderType, SourceProvider
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.services.health_check import (
    HealthCheckItem,
    HealthCheckReport,
    HealthCheckService,
    HealthCheckSeverity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_health_mirror(db: AsyncSession) -> Mirror:
    """Create a full mirror chain: Credential → SourceProvider → SourceGroup →
    SourceRepository → SyncGroup → Pipeline → GitlabInstance → Mirror."""
    # Credential
    cred = Credential(
        name="test-cred",
        credential_type=CredentialType.github_token,
        provider="github",
        encrypted_secret="gAAAAAB...",  # dummy encrypted token
        status_flag=0,
    )
    db.add(cred)
    await db.flush()

    # SourceProvider
    sp = SourceProvider(
        credential_id=cred.id,
        provider_type=ProviderType.github,
        label="test-provider",
    )
    db.add(sp)
    await db.flush()

    # SourceGroup
    sg = SourceGroup(
        external_id="testorg",
        name="Test Org",
        full_path="testorg",
    )
    db.add(sg)
    await db.flush()

    # SourceRepository
    sr = SourceRepository(
        source_group_id=sg.id,
        external_id="12345",
        name="test-repo",
        full_name="testorg/test-repo",
        clone_url_https="https://github.com/testorg/test-repo.git",
    )
    db.add(sr)
    await db.flush()

    # GitlabInstance
    instance = GitlabInstance(
        url="https://gitlab.example.com",
        token="gAAAAAB...",  # dummy encrypted token
        verify_ssl=True,
        name="test-instance",
    )
    db.add(instance)
    await db.flush()

    # Pipeline
    pipeline = Pipeline(
        name="test-pipeline",
        gitlab_instance_id=instance.id,
        ref="main",
    )
    db.add(pipeline)
    await db.flush()

    # SyncGroup
    sync_group = SyncGroup(
        name="test-sync-group",
        description="Test group",
        is_default=False,
        pipeline_id=pipeline.id,
    )
    db.add(sync_group)
    await db.flush()

    # Mirror
    mirror = Mirror(
        source_repository_id=sr.id,
        sync_group_id=sync_group.id,
        target_namespace="testns",
        target_project_name="test-repo",
        target_project_id="42",
        status_flag=0,
        status_text="OK",
    )
    db.add(mirror)
    await db.commit()
    await db.refresh(mirror)
    return mirror


# ---------------------------------------------------------------------------
# Tests: HealthCheckReport
# ---------------------------------------------------------------------------


class TestHealthCheckReport:
    """Tests for HealthCheckReport dataclass and overall severity aggregation."""

    def test_overall_ok_when_empty_items(self):
        """overall returns OK when there are no items."""
        report = HealthCheckReport()
        assert report.overall == HealthCheckSeverity.OK

    def test_overall_ok_when_all_ok(self):
        """overall returns OK when all items are OK."""
        report = HealthCheckReport(
            items=[
                HealthCheckItem(component="a", severity=HealthCheckSeverity.OK, message="ok"),
                HealthCheckItem(component="b", severity=HealthCheckSeverity.OK, message="ok"),
            ]
        )
        assert report.overall == HealthCheckSeverity.OK

    def test_overall_warning_when_mixed(self):
        """overall returns WARNING when WARNING is worst severity."""
        report = HealthCheckReport(
            items=[
                HealthCheckItem(component="a", severity=HealthCheckSeverity.OK, message="ok"),
                HealthCheckItem(
                    component="b", severity=HealthCheckSeverity.WARNING, message="warn"
                ),
            ]
        )
        assert report.overall == HealthCheckSeverity.WARNING

    def test_overall_error_when_any_error(self):
        """overall returns ERROR when at least one item is ERROR."""
        report = HealthCheckReport(
            items=[
                HealthCheckItem(component="a", severity=HealthCheckSeverity.OK, message="ok"),
                HealthCheckItem(component="b", severity=HealthCheckSeverity.ERROR, message="fail"),
            ]
        )
        assert report.overall == HealthCheckSeverity.ERROR

    def test_overall_error_trumps_warning(self):
        """overall returns ERROR even if WARNING items are present."""
        report = HealthCheckReport(
            items=[
                HealthCheckItem(
                    component="a", severity=HealthCheckSeverity.WARNING, message="warn"
                ),
                HealthCheckItem(component="b", severity=HealthCheckSeverity.ERROR, message="fail"),
            ]
        )
        assert report.overall == HealthCheckSeverity.ERROR


# ---------------------------------------------------------------------------
# Tests: HealthCheckService.check_system
# ---------------------------------------------------------------------------


class TestCheckSystem:
    """Tests for HealthCheckService.check_system()."""

    @pytest.mark.asyncio
    async def test_check_system_empty_db(self, db_session: AsyncSession):
        """check_system reports WARNING on an empty database (nothing configured)."""
        report = await HealthCheckService.check_system(db_session)
        assert report.overall == HealthCheckSeverity.WARNING

    @pytest.mark.asyncio
    async def test_check_system_with_credentials(self, db_session: AsyncSession):
        """check_system checks credentials."""
        cred = Credential(
            name="test-cred",
            credential_type=CredentialType.github_token,
            provider="github",
            encrypted_secret="gAAAAAB...",
            status_flag=0,
        )
        db_session.add(cred)
        await db_session.commit()

        # Encrypted secret will fail decryption in test, but check should handle it
        report = await HealthCheckService.check_system(db_session)
        assert isinstance(report.items, list)
        # There should be at least one item for the credential
        assert len(report.items) >= 1


# ---------------------------------------------------------------------------
# Tests: HealthCheckService.check_sync_group
# ---------------------------------------------------------------------------


class TestCheckSyncGroup:
    """Tests for HealthCheckService.check_sync_group()."""

    @pytest.mark.asyncio
    async def test_check_sync_group_not_found(self, db_session: AsyncSession):
        """check_sync_group returns ERROR item for non-existent group."""
        report = await HealthCheckService.check_sync_group(db_session, 99999)
        assert report.overall == HealthCheckSeverity.ERROR
        assert any(
            "not found" in item.message.lower()
            for item in report.items
            if item.severity == HealthCheckSeverity.ERROR
        )


# ---------------------------------------------------------------------------
# Tests: HealthCheckService.check_mirror
# ---------------------------------------------------------------------------


class TestCheckMirror:
    """Tests for HealthCheckService.check_mirror()."""

    @pytest.mark.asyncio
    async def test_check_mirror_not_found(self, db_session: AsyncSession):
        """check_mirror returns ERROR item for non-existent mirror."""
        report = await HealthCheckService.check_mirror(db_session, 99999)
        assert report.overall == HealthCheckSeverity.ERROR
        assert any(
            "not found" in item.message.lower()
            for item in report.items
            if item.severity == HealthCheckSeverity.ERROR
        )

    @pytest.mark.asyncio
    async def test_check_mirror_with_data(self, db_session: AsyncSession):
        """check_mirror checks credential, source, and target for a mirror."""
        mirror = await _seed_health_mirror(db_session)

        # Mock decrypt_secret and source provider
        with (
            patch("app.services.health_check.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.health_check.create_source_provider",
                new_callable=AsyncMock,
            ) as mock_create,
            patch(
                "app.services.health_check._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class,
        ):
            mock_provider = AsyncMock()
            mock_provider.check_access.return_value = True
            mock_provider.get_repository.return_value = {
                "full_name": "testorg/test-repo",
                "default_branch": "main",
            }
            mock_provider.get_commit_info.return_value = {
                "sha": "abc123def456",
                "date": datetime.now(UTC),
                "author": "test",
            }
            mock_create.return_value = mock_provider

            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_project.id = 42
            mock_project.path_with_namespace = "testns/test-repo"
            mock_gl.projects.get.return_value = mock_project
            mock_gl_class.return_value = mock_gl

            report = await HealthCheckService.check_mirror(db_session, mirror.id)

        assert report.mirror_id == mirror.id
        assert isinstance(report.items, list)
        assert len(report.items) > 0
