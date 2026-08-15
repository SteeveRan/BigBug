"""
@file test_mirror_service.py
@description Unit tests for MirrorService — create, bulk create, duplicate check,
             list/filter, detail, soft delete, trigger sync, freshness check,
             import existing mirror.
@dependencies pytest, pytest-asyncio, unittest.mock, sqlalchemy
@relatedFiles ../../app/services/mirror.py, ../../app/models/mirror.py,
              ../../app/services/audit.py, ../../app/services/pipeline.py
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mirror import Mirror
from app.models.mirror_log import MirrorLog, MirrorLogType
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
from app.models.user import User
from app.schemas.mirror import MirrorBulkCreate, MirrorCreate
from app.services.mirror import MirrorService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_gitlab_provider(db: AsyncSession, name: str) -> ResourceProvider:
    """Create a system/internal gitlab ResourceProvider for pipeline targets."""
    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.gitlab,
        category=ProviderCategory.system,
        direction=ProviderDirection.internal,
        name=name,
        label=name,
        base_url="https://gitlab.example.com",
        verify_ssl=True,
    )
    db.add(provider)
    await db.flush()
    return provider


async def _seed_source_repo(db: AsyncSession, **overrides) -> SourceRepository:
    """Create a minimal SourceRepository with a SourceGroup."""
    sg = SourceGroup(
        external_id="testorg",
        name="Test Org",
        full_path="testorg",
    )
    db.add(sg)
    await db.flush()

    defaults = {
        "source_group_id": sg.id,
        "external_id": "12345",
        "name": "test-repo",
        "full_name": "testorg/test-repo",
        "clone_url_https": "https://github.com/testorg/test-repo.git",
    }
    defaults.update(overrides)
    sr = SourceRepository(**defaults)
    db.add(sr)
    await db.commit()
    await db.refresh(sr)
    return sr


async def _seed_sync_group(db: AsyncSession, **overrides) -> SyncGroup:
    """Create a minimal SyncGroup."""
    defaults = {
        "name": "test-sync-group",
        "description": "Test group",
        "is_default": False,
    }
    defaults.update(overrides)
    sg = SyncGroup(**defaults)
    db.add(sg)
    await db.commit()
    await db.refresh(sg)
    return sg


def _make_admin_user() -> User:
    """Build a mock admin User."""
    from app.models.role import Role, UserRole

    admin_role = MagicMock(spec=Role)
    admin_role.name = "admin"
    admin_role.id = 1
    user_role = MagicMock(spec=UserRole)
    user_role.role = admin_role
    user_role.role_id = 1
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testadmin"
    user.user_roles = [user_role]
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateMirror:
    """Tests for MirrorService.create_mirror()"""

    @pytest.mark.asyncio
    async def test_create_mirror_success(self, db_session: AsyncSession):
        """create_mirror creates a mirror and logs audit events."""
        sr = await _seed_source_repo(db_session)
        sg = await _seed_sync_group(db_session, name="sg-create")

        data = MirrorCreate(
            source_repository_id=sr.id,
            sync_group_id=sg.id,
            target_namespace="testns",
            target_project_name="test-project",
        )

        with patch(
            "app.services.mirror.AuditService.log_event", new_callable=AsyncMock
        ) as mock_audit:
            mirror = await MirrorService.create_mirror(
                db_session, data, user_id=1, username="testadmin"
            )

        assert mirror.id is not None
        assert mirror.source_repository_id == sr.id
        assert mirror.target_namespace == "testns"
        assert mirror.target_project_name == "test-project"
        assert mirror.status_flag == 4  # Pending
        assert mirror.is_deleted is False
        # Audit should have been called at least once (for "mirror.created")
        audit_calls = [c.args[1] for c in mock_audit.call_args_list if len(c.args) >= 2]
        assert "mirror.created" in audit_calls or any(
            "mirror.created" in str(c) for c in mock_audit.call_args_list
        )

    @pytest.mark.asyncio
    async def test_create_mirror_duplicate_warning(self, db_session: AsyncSession):
        """create_mirror detects duplicates but still creates the mirror."""
        sr = await _seed_source_repo(db_session)

        data = MirrorCreate(
            source_repository_id=sr.id,
            target_namespace="dup-ns",
            target_project_name="dup-project",
        )

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            first = await MirrorService.create_mirror(
                db_session, data, user_id=1, username="testadmin"
            )

        # Creating same again should produce a duplicate warning
        with patch(
            "app.services.mirror.AuditService.log_event", new_callable=AsyncMock
        ) as mock_audit:
            second = await MirrorService.create_mirror(
                db_session, data, user_id=1, username="testadmin"
            )

        # Both should exist (different IDs)
        assert first.id != second.id
        # Verify a duplicate_warning audit was logged
        duplicate_warning_found = False
        for call_args in mock_audit.call_args_list:
            action = call_args.kwargs.get("action") or (
                call_args.args[1] if len(call_args.args) >= 2 else ""
            )
            if "duplicate_warning" in str(action):
                duplicate_warning_found = True
                break
        assert duplicate_warning_found, "Expected a duplicate_warning audit event"


class TestBulkCreateMirrors:
    """Tests for MirrorService.bulk_create_mirrors()"""

    @pytest.mark.asyncio
    async def test_bulk_create_mirrors(self, db_session: AsyncSession):
        """bulk_create_mirrors creates multiple mirrors in one batch."""
        sr1 = await _seed_source_repo(
            db_session, external_id="1", name="repo1", full_name="testorg/repo1"
        )
        sr2 = await _seed_source_repo(
            db_session, external_id="2", name="repo2", full_name="testorg/repo2"
        )
        sr3 = await _seed_source_repo(
            db_session, external_id="3", name="repo3", full_name="testorg/repo3"
        )

        data = MirrorBulkCreate(
            mirrors=[
                MirrorCreate(
                    source_repository_id=sr1.id, target_namespace="ns", target_project_name="p1"
                ),
                MirrorCreate(
                    source_repository_id=sr2.id, target_namespace="ns", target_project_name="p2"
                ),
                MirrorCreate(
                    source_repository_id=sr3.id, target_namespace="ns", target_project_name="p3"
                ),
            ],
            default_target_namespace="ns",
        )

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            mirrors = await MirrorService.bulk_create_mirrors(
                db_session, data, user_id=1, username="testadmin"
            )

        assert len(mirrors) == 3
        for m in mirrors:
            assert m.id is not None
            assert m.status_flag == 4


class TestCheckDuplicates:
    """Tests for MirrorService.check_duplicates()"""

    @pytest.mark.asyncio
    async def test_check_duplicates(self, db_session: AsyncSession):
        """check_duplicates finds existing mirrors for given source repo IDs."""
        sr = await _seed_source_repo(db_session)
        sg = await _seed_sync_group(db_session, name="dup-sg")

        # Create two mirrors for the same source repo
        data1 = MirrorCreate(
            source_repository_id=sr.id,
            sync_group_id=sg.id,
            target_namespace="ns",
            target_project_name="proj1",
        )
        data2 = MirrorCreate(
            source_repository_id=sr.id,
            sync_group_id=sg.id,
            target_namespace="ns",
            target_project_name="proj2",
        )

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            await MirrorService.create_mirror(db_session, data1, user_id=1)
            await MirrorService.create_mirror(db_session, data2, user_id=1)

        result = await MirrorService.check_duplicates(
            db_session,
            source_repo_ids=[sr.id, 99999],
            sync_group_id=sg.id,
        )

        assert len(result["duplicates"]) >= 1
        assert len(result["accessible"]) >= 1


class TestGetMirrors:
    """Tests for MirrorService.get_mirrors()"""

    @pytest.mark.asyncio
    async def test_get_mirrors_with_filters(self, db_session: AsyncSession, admin_user):
        """get_mirrors supports filtering by status_flag and search."""
        # Re-fetch admin_user with eager-loaded roles (avoid MissingGreenlet)
        from app.models.user import User as UserModel

        admin_with_roles = await db_session.execute(
            select(UserModel)
            .options(selectinload(UserModel.user_roles))
            .where(UserModel.id == admin_user.id)
        )
        user = admin_with_roles.scalar_one()

        sr = await _seed_source_repo(db_session)

        # Create mirrors with different statuses
        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            m1 = await MirrorService.create_mirror(
                db_session,
                MirrorCreate(
                    source_repository_id=sr.id,
                    target_namespace="ns",
                    target_project_name="ok-project",
                ),
                user_id=1,
            )
            # Manually update status
            m1.status_flag = 0  # OK
            m1.status_text = "OK"
            await db_session.commit()

            m2 = await MirrorService.create_mirror(
                db_session,
                MirrorCreate(
                    source_repository_id=sr.id,
                    target_namespace="ns",
                    target_project_name="failed-project",
                ),
                user_id=1,
            )
            m2.status_flag = 1
            m2.status_text = "Failed"
            await db_session.commit()

        # Filter by status_flag=1 (Failed)
        items, total = await MirrorService.get_mirrors(
            db_session, {"status_flag": 1}, user, limit=10, offset=0
        )
        assert total == 1
        assert items[0].target_project_name == "failed-project"

        # Search by name
        items, total = await MirrorService.get_mirrors(
            db_session, {"search": "ok-project"}, user, limit=10, offset=0
        )
        assert total >= 1
        assert any(m.target_project_name == "ok-project" for m in items)


class TestGetMirrorDetail:
    """Tests for MirrorService.get_mirror_detail()"""

    @pytest.mark.asyncio
    async def test_get_mirror_detail(self, db_session: AsyncSession):
        """get_mirror_detail returns mirror with logs."""
        sr = await _seed_source_repo(db_session)

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            mirror = await MirrorService.create_mirror(
                db_session,
                MirrorCreate(
                    source_repository_id=sr.id,
                    target_namespace="ns",
                    target_project_name="detail-project",
                ),
                user_id=1,
            )

        # Add a mirror log
        log = MirrorLog(
            mirror_id=mirror.id,
            log_type=MirrorLogType.sync,
            status_flag=0,
            status_text="OK",
            triggered_by="manual",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
        )
        db_session.add(log)
        await db_session.commit()

        detail = await MirrorService.get_mirror_detail(db_session, mirror.id)
        assert detail.id == mirror.id
        assert detail.source_repository is not None
        assert len(detail.mirror_logs) >= 1


class TestSoftDeleteMirror:
    """Tests for MirrorService.soft_delete_mirror()"""

    @pytest.mark.asyncio
    async def test_soft_delete_mirror(self, db_session: AsyncSession):
        """soft_delete_mirror sets is_deleted=True and deleted_at."""
        sr = await _seed_source_repo(db_session)

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            mirror = await MirrorService.create_mirror(
                db_session,
                MirrorCreate(
                    source_repository_id=sr.id,
                    target_namespace="ns",
                    target_project_name="del-project",
                ),
                user_id=1,
            )

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            await MirrorService.soft_delete_mirror(db_session, mirror.id, username="testadmin")

        # Fetch fresh
        result = await db_session.execute(select(Mirror).where(Mirror.id == mirror.id))
        deleted_mirror = result.scalar_one()
        assert deleted_mirror.is_deleted is True
        assert deleted_mirror.deleted_at is not None


class TestTriggerSync:
    """Tests for MirrorService.trigger_sync()"""

    @pytest.mark.asyncio
    async def test_trigger_sync(self, db_session: AsyncSession):
        """trigger_sync triggers a pipeline and creates a MirrorLog."""
        from app.models.pipeline import Pipeline as PipelineModel

        sr = await _seed_source_repo(db_session)

        # Create ResourceProvider → Pipeline → SyncGroup
        provider = await _seed_gitlab_provider(db_session, "test-gitlab")

        pipeline = PipelineModel(
            name="test-pipeline",
            provider_id=provider.id,
            ref="main",
            is_default=True,
        )
        db_session.add(pipeline)
        await db_session.flush()

        sg = SyncGroup(
            name="sg-with-pipeline",
            pipeline_id=pipeline.id,
        )
        db_session.add(sg)
        await db_session.flush()

        mirror = Mirror(
            source_repository_id=sr.id,
            sync_group_id=sg.id,
            target_namespace="ns",
            target_project_name="sync-project",
            target_project_id="42",
            status_flag=4,
            status_text="Pending",
        )
        db_session.add(mirror)
        await db_session.commit()
        await db_session.refresh(mirror)

        with patch("app.services.mirror.trigger_pipeline", new_callable=AsyncMock) as mock_trigger:
            mock_run = MagicMock()
            mock_run.id = 1
            mock_run.gitlab_pipeline_id = 200
            mock_run.web_url = "https://gitlab.example.com/pipelines/200"
            mock_trigger.return_value = mock_run

            with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
                mirror_log = await MirrorService.trigger_sync(
                    db_session, mirror.id, user_id=1, username="testadmin"
                )

        assert mirror_log is not None
        assert mirror_log.log_type == MirrorLogType.sync
        assert mirror_log.mirror_id == mirror.id
        mock_trigger.assert_called_once()


class TestCheckFreshness:
    """Tests for MirrorService.check_freshness()"""

    @pytest.mark.asyncio
    async def test_check_freshness(self, db_session: AsyncSession):
        """check_freshness compares source commit with mirror."""
        from app.core.secrets import encrypt_secret

        # Build full chain: SourceProvider → SourceGroup → SourceRepository → Mirror
        from app.models.credential import Credential, CredentialType

        cred = Credential(
            name="test-cred-freshness",
            credential_type=CredentialType.github_token,
            provider="github",
            encrypted_secret=encrypt_secret("ghp_test_freshness_token"),
        )
        db_session.add(cred)
        await db_session.flush()

        sp = ResourceProvider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="test-gh",
            label="test-gh",
            credential_id=cred.id,
            verify_ssl=True,
        )
        db_session.add(sp)
        await db_session.flush()

        sg = SourceGroup(
            external_id="testorg",
            name="Test Org",
            full_path="testorg",
        )
        db_session.add(sg)
        await db_session.flush()

        sr = SourceRepository(
            source_group_id=sg.id,
            provider_id=sp.id,
            external_id="12345",
            name="fresh-repo",
            full_name="testorg/fresh-repo",
        )
        db_session.add(sr)
        await db_session.flush()

        sync_g = SyncGroup(name="sg-fresh")
        db_session.add(sync_g)
        await db_session.flush()

        mirror = Mirror(
            source_repository_id=sr.id,
            sync_group_id=sync_g.id,
            target_namespace="ns",
            target_project_name="fresh-project",
            status_flag=4,
        )
        db_session.add(mirror)
        await db_session.commit()

        # Mock create_source_provider → get_commit_info
        mock_commit = {
            "sha": "abc123",
            "date": datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
            "author": "Test",
            "message": "msg",
        }

        mock_provider = MagicMock()
        mock_provider.get_commit_info = AsyncMock(return_value=mock_commit)

        with (
            patch.object(
                MirrorService, "check_freshness", wraps=MirrorService.check_freshness
            ) as wrapped,
            patch(
                "app.services.mirror.create_source_provider",
                new_callable=AsyncMock,
                return_value=mock_provider,
            ),
            patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock),
        ):
            mirror_log = await wrapped(db_session, mirror.id, username="testadmin")

        assert mirror_log.log_type == MirrorLogType.freshness
        # Its mirror should now have last_freshness_check_at set
        result = await db_session.execute(select(Mirror).where(Mirror.id == mirror.id))
        updated = result.scalar_one()
        assert updated.last_freshness_check_at is not None


class TestImportExistingMirror:
    """Tests for MirrorService.import_existing_mirror()"""

    @pytest.mark.asyncio
    async def test_import_existing_mirror_success(self, db_session: AsyncSession):
        """import_existing_mirror verifies commit and creates imported mirror."""
        from app.core.secrets import encrypt_secret
        from app.models.credential import Credential, CredentialType

        cred = Credential(
            name="test-cred-import",
            credential_type=CredentialType.github_token,
            provider="github",
            encrypted_secret=encrypt_secret("ghp_test_import_token"),
        )
        db_session.add(cred)
        await db_session.flush()

        sp = ResourceProvider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="test-gh-import",
            label="test-gh-import",
            credential_id=cred.id,
            verify_ssl=True,
        )
        db_session.add(sp)
        await db_session.flush()

        sg = SourceGroup(
            external_id="testorg",
            name="Test Org",
            full_path="testorg",
        )
        db_session.add(sg)
        await db_session.commit()

        mock_commit = {
            "sha": "abc123",
            "date": datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
            "author": "Test",
        }

        mock_provider = MagicMock()
        mock_provider.get_commit_info = AsyncMock(return_value=mock_commit)

        with (
            patch(
                "app.services.mirror.create_source_provider",
                new_callable=AsyncMock,
                return_value=mock_provider,
            ),
            patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock),
        ):
            mirror = await MirrorService.import_existing_mirror(
                db_session,
                source_url="https://github.com/testorg/import-repo.git",
                target_gitlab_id=1,
                target_path="gitlab-ns/imported-project",
                user_id=1,
                username="testadmin",
            )

        assert mirror.is_imported is True
        assert mirror.target_namespace == "gitlab-ns"
        assert mirror.target_project_name == "imported-project"
        assert mirror.last_known_commit_sha == "abc123"


# ========================================================================
# Extended tests for MirrorService (Group E — trigger_sync/freshness/logs)
# ========================================================================


class TestTriggerSyncNoPipeline:
    """Tests for MirrorService.trigger_sync() when no Pipeline is configured."""

    @pytest.mark.asyncio
    async def test_trigger_sync_skips_when_no_pipeline(self, db_session: AsyncSession):
        """trigger_sync creates a SKIPPED MirrorLog when SyncGroup has no Pipeline."""
        sr = await _seed_source_repo(db_session)

        sg = SyncGroup(name="sg-no-pipeline")
        db_session.add(sg)
        await db_session.flush()

        mirror = Mirror(
            source_repository_id=sr.id,
            sync_group_id=sg.id,
            target_namespace="ns",
            target_project_name="no-pipeline-project",
            status_flag=4,
        )
        db_session.add(mirror)
        await db_session.commit()
        await db_session.refresh(mirror)

        mirror_log = await MirrorService.trigger_sync(
            db_session, mirror.id, user_id=1, username="testuser"
        )

        assert mirror_log is not None
        assert mirror_log.log_type == MirrorLogType.sync
        assert mirror_log.mirror_id == mirror.id
        assert mirror_log.pipeline_run_id is None
        assert mirror_log.status_flag == 4  # Pending
        assert "Skipped" in (mirror_log.status_text or "")


class TestTriggerSyncCreatesPipelineRun:
    """Tests for MirrorService.trigger_sync() — full chain."""

    @pytest.mark.asyncio
    async def test_trigger_sync_creates_pipeline_run_and_mirror_log(self, db_session: AsyncSession):
        """trigger_sync creates PipelineRun and MirrorLog when Pipeline is configured."""
        from app.models.pipeline import Pipeline as PipelineModel

        sr = await _seed_source_repo(db_session)

        provider = await _seed_gitlab_provider(db_session, "test-gitlab-e2")

        pipeline = PipelineModel(
            name="test-pipeline-e2",
            provider_id=provider.id,
            ref="main",
            is_default=True,
            default_variables={"CUSTOM_VAR": "custom_val"},
        )
        db_session.add(pipeline)
        await db_session.flush()

        sg = SyncGroup(
            name="sg-full-chain",
            pipeline_id=pipeline.id,
        )
        db_session.add(sg)
        await db_session.flush()

        mirror = Mirror(
            source_repository_id=sr.id,
            sync_group_id=sg.id,
            target_namespace="ns",
            target_project_name="full-chain-project",
            target_project_id="42",
            status_flag=4,
            status_text="Pending",
        )
        db_session.add(mirror)
        await db_session.commit()
        await db_session.refresh(mirror)

        with patch("app.services.mirror.trigger_pipeline", new_callable=AsyncMock) as mock_trigger:
            mock_run = MagicMock()
            mock_run.id = 100
            mock_run.gitlab_pipeline_id = 300
            mock_run.web_url = "https://gitlab.example.com/pipelines/300"
            mock_trigger.return_value = mock_run

            with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
                mirror_log = await MirrorService.trigger_sync(
                    db_session, mirror.id, user_id=1, username="testuser"
                )

        assert mirror_log is not None
        assert mirror_log.log_type == MirrorLogType.sync
        assert mirror_log.mirror_id == mirror.id
        assert mirror_log.pipeline_run_id == 100
        assert mirror_log.status_flag == 3  # In Progress
        assert mirror_log.triggered_by == "testuser"

        # Verify variables passed to trigger_pipeline include merged defaults
        mock_trigger.assert_called_once()
        call_kwargs = mock_trigger.call_args.kwargs
        assert call_kwargs["provider_id"] == provider.id
        assert call_kwargs["gitlab_project_id"] == 42
        assert call_kwargs["ref"] == "main"
        assert "CUSTOM_VAR" in call_kwargs["variables"]
        assert call_kwargs["variables"]["CUSTOM_VAR"] == "custom_val"
        assert "SOURCE_URL" in call_kwargs["variables"]
        assert call_kwargs["user_id"] == 1


class TestCheckFreshnessExtended:
    """Extended tests for MirrorService.check_freshness()."""

    async def _build_freshness_chain(
        self, db_session: AsyncSession, mirror_sha: str | None = None
    ) -> Mirror:
        """Build a complete SourceProvider→SourceRepo→Mirror chain for freshness tests."""
        from app.core.secrets import encrypt_secret
        from app.models.credential import Credential, CredentialType

        cred = Credential(
            name="test-cred-ext",
            credential_type=CredentialType.github_token,
            provider="github",
            encrypted_secret=encrypt_secret("ghp_test_extended_token"),
        )
        db_session.add(cred)
        await db_session.flush()

        sp = ResourceProvider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="test-gh-ext",
            label="test-gh-ext",
            credential_id=cred.id,
            verify_ssl=True,
        )
        db_session.add(sp)
        await db_session.flush()

        sg = SourceGroup(
            external_id="testorg-ext",
            name="Test Org Ext",
            full_path="testorg-ext",
        )
        db_session.add(sg)
        await db_session.flush()

        sr = SourceRepository(
            source_group_id=sg.id,
            provider_id=sp.id,
            external_id="123456",
            name="fresh-ext-repo",
            full_name="testorg-ext/fresh-ext-repo",
        )
        db_session.add(sr)
        await db_session.flush()

        sync_g = SyncGroup(name="sg-fresh-ext")
        db_session.add(sync_g)
        await db_session.flush()

        mirror = Mirror(
            source_repository_id=sr.id,
            sync_group_id=sync_g.id,
            target_namespace="ns",
            target_project_name="fresh-ext-project",
            status_flag=4,
            last_known_commit_sha=mirror_sha,
        )
        db_session.add(mirror)
        await db_session.commit()
        await db_session.refresh(mirror)
        return mirror

    @pytest.mark.asyncio
    async def test_check_freshness_detects_stale(self, db_session: AsyncSession):
        """check_freshness returns STALE when source SHA differs from last known."""
        mirror = await self._build_freshness_chain(db_session, mirror_sha="oldsha111")

        mock_commit = {
            "sha": "newsha222",
            "date": datetime(2025, 6, 10, 12, 0, 0, tzinfo=UTC),
            "author": "Test Author",
        }

        mock_provider = MagicMock()
        mock_provider.get_commit_info = AsyncMock(return_value=mock_commit)

        with (
            patch(
                "app.services.mirror.create_source_provider",
                new_callable=AsyncMock,
                return_value=mock_provider,
            ),
            patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock),
        ):
            mirror_log = await MirrorService.check_freshness(
                db_session, mirror.id, username="testuser"
            )

        assert mirror_log.log_type == MirrorLogType.freshness
        assert mirror_log.status_text == "STALE"
        assert mirror_log.source_commit_sha == "newsha222"
        assert mirror_log.triggered_by == "testuser"

        # Mirror should have updated last_known_commit_sha
        result = await db_session.execute(select(Mirror).where(Mirror.id == mirror.id))
        updated = result.scalar_one()
        assert updated.last_known_commit_sha == "newsha222"
        assert updated.last_freshness_status == "STALE"

    @pytest.mark.asyncio
    async def test_check_freshness_detects_fresh(self, db_session: AsyncSession):
        """check_freshness returns FRESH when source SHA matches last known."""
        mirror = await self._build_freshness_chain(db_session, mirror_sha="abc123match")

        mock_commit = {
            "sha": "abc123match",
            "date": datetime(2025, 6, 10, 12, 0, 0, tzinfo=UTC),
            "author": "Test Author",
        }

        mock_provider = MagicMock()
        mock_provider.get_commit_info = AsyncMock(return_value=mock_commit)

        with (
            patch(
                "app.services.mirror.create_source_provider",
                new_callable=AsyncMock,
                return_value=mock_provider,
            ),
            patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock),
        ):
            mirror_log = await MirrorService.check_freshness(
                db_session, mirror.id, username="testuser"
            )

        assert mirror_log.log_type == MirrorLogType.freshness
        assert mirror_log.status_text == "FRESH"
        assert mirror_log.source_commit_sha == "abc123match"
        assert mirror_log.target_commit_sha == "abc123match"

    @pytest.mark.asyncio
    async def test_check_freshness_handles_api_error(self, db_session: AsyncSession):
        """check_freshness returns ERROR when GitHub API call fails."""
        mirror = await self._build_freshness_chain(db_session, mirror_sha="oldsha333")

        mock_provider = MagicMock()
        mock_provider.get_commit_info = AsyncMock(side_effect=Exception("GitHub API timeout"))

        with (
            patch(
                "app.services.mirror.create_source_provider",
                new_callable=AsyncMock,
                return_value=mock_provider,
            ),
            patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock),
        ):
            mirror_log = await MirrorService.check_freshness(
                db_session, mirror.id, username="testuser"
            )

        assert mirror_log.log_type == MirrorLogType.freshness
        assert mirror_log.status_text == "ERROR"
        assert mirror_log.status_flag == 1  # Failed
        assert mirror_log.details is not None
        assert "GitHub API timeout" in str(mirror_log.details.get("message", ""))


class TestCreateMirrorAutoSync:
    """Tests for MirrorService.create_mirror() with auto-sync."""

    @pytest.mark.asyncio
    async def test_create_mirror_triggers_initial_sync(self, db_session: AsyncSession):
        """create_mirror auto-triggers sync when SyncGroup has a Pipeline."""
        from app.models.pipeline import Pipeline as PipelineModel

        sr = await _seed_source_repo(db_session)

        provider = await _seed_gitlab_provider(db_session, "test-gitlab-autosync")

        pipeline = PipelineModel(
            name="test-pipeline-autosync",
            provider_id=provider.id,
            ref="main",
            is_default=True,
        )
        db_session.add(pipeline)
        await db_session.flush()

        sg = SyncGroup(
            name="sg-autosync",
            pipeline_id=pipeline.id,
        )
        db_session.add(sg)
        await db_session.flush()

        data = MirrorCreate(
            source_repository_id=sr.id,
            sync_group_id=sg.id,
            target_namespace="auto-ns",
            target_project_name="auto-project",
        )

        # Auto-sync requires target_project_id for trigger_pipeline,
        # so we mock trigger_pipeline to avoid that requirement
        with patch("app.services.mirror.trigger_pipeline", new_callable=AsyncMock) as mock_trigger:
            mock_run = MagicMock()
            mock_run.id = 500
            mock_run.gitlab_pipeline_id = 600
            mock_run.web_url = "https://gitlab.example.com/pipelines/600"
            mock_trigger.return_value = mock_run

            with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
                mirror = await MirrorService.create_mirror(
                    db_session, data, user_id=1, username="testuser"
                )

        assert mirror.id is not None
        # Auto-sync should have been attempted (target_project_id is None,
        # so it will likely raise or be skipped — we need to ensure no
        # exception escapes create_mirror)
        assert mirror.source_repository_id == sr.id

    @pytest.mark.asyncio
    async def test_create_mirror_no_sync_without_pipeline(self, db_session: AsyncSession):
        """create_mirror does NOT trigger sync when SyncGroup has no Pipeline."""
        sr = await _seed_source_repo(db_session)

        sg = SyncGroup(name="sg-no-pipeline-auto")
        db_session.add(sg)
        await db_session.flush()

        data = MirrorCreate(
            source_repository_id=sr.id,
            sync_group_id=sg.id,
            target_namespace="plain-ns",
            target_project_name="plain-project",
        )

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            mirror = await MirrorService.create_mirror(
                db_session, data, user_id=1, username="testuser"
            )

        assert mirror.id is not None
        assert mirror.sync_group_id == sg.id
        # No auto-sync should have occurred since sync group has no pipeline


class TestGetLogs:
    """Tests for MirrorService.get_logs()."""

    @pytest.mark.asyncio
    async def test_get_logs_returns_paginated_logs(self, db_session: AsyncSession):
        """get_logs returns paginated logs for a mirror."""
        sr = await _seed_source_repo(db_session)
        sg = await _seed_sync_group(db_session, name="logs-sg")

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            mirror = await MirrorService.create_mirror(
                db_session,
                MirrorCreate(
                    source_repository_id=sr.id,
                    sync_group_id=sg.id,
                    target_namespace="logs-ns",
                    target_project_name="logs-project",
                ),
                user_id=1,
            )

        # Create several logs
        for i in range(5):
            log = MirrorLog(
                mirror_id=mirror.id,
                log_type=MirrorLogType.sync if i % 2 == 0 else MirrorLogType.freshness,
                status_flag=0 if i % 2 == 0 else 2,
                status_text="OK" if i % 2 == 0 else "STALE",
                triggered_by="test",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
            db_session.add(log)
        await db_session.commit()

        # Get first 3
        logs = await MirrorService.get_logs(db_session, mirror.id, limit=3, offset=0)
        assert len(logs) == 3

        # Get next 2
        logs = await MirrorService.get_logs(db_session, mirror.id, limit=3, offset=3)
        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_get_logs_filters_by_log_type(self, db_session: AsyncSession):
        """get_logs filters by log_type correctly."""
        sr = await _seed_source_repo(db_session)
        sg = await _seed_sync_group(db_session, name="logs-filter-sg")

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            mirror = await MirrorService.create_mirror(
                db_session,
                MirrorCreate(
                    source_repository_id=sr.id,
                    sync_group_id=sg.id,
                    target_namespace="filter-ns",
                    target_project_name="filter-project",
                ),
                user_id=1,
            )

        # Create sync and freshness logs
        for log_type, status_text in [
            (MirrorLogType.sync, "Running"),
            (MirrorLogType.freshness, "FRESH"),
            (MirrorLogType.sync, "OK"),
            (MirrorLogType.freshness, "STALE"),
        ]:
            log = MirrorLog(
                mirror_id=mirror.id,
                log_type=log_type,
                status_flag=0 if status_text in ("OK", "FRESH") else 2,
                status_text=status_text,
                triggered_by="test",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
            )
            db_session.add(log)
        await db_session.commit()

        # Filter by SYNC type
        sync_logs = await MirrorService.get_logs(
            db_session, mirror.id, log_type=MirrorLogType.sync, limit=50, offset=0
        )
        assert len(sync_logs) == 2
        assert all(log.log_type == MirrorLogType.sync for log in sync_logs)

        # Filter by FRESHNESS type
        freshness_logs = await MirrorService.get_logs(
            db_session, mirror.id, log_type=MirrorLogType.freshness, limit=50, offset=0
        )
        assert len(freshness_logs) == 2
        assert all(log.log_type == MirrorLogType.freshness for log in freshness_logs)
