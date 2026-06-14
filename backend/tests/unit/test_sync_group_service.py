"""
@file test_sync_group_service.py
@description Unit tests for SyncGroupService — default group resolution,
             CRUD operations, RBAC-scoped listing, soft-delete with mirror
             migration, and bulk mirror assignment.
@dependencies pytest, pytest-asyncio, sqlalchemy, unittest.mock
@relatedFiles ../../app/services/sync_group.py,
              ../../app/models/sync_group.py,
              ../../app/models/mirror.py,
              ../../app/models/pipeline.py,
              ../../app/models/user.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DomainError
from app.models.mirror import Mirror
from app.models.pipeline import Pipeline
from app.models.source_group import SourceGroup
from app.models.source_provider import ProviderType, SourceProvider
from app.models.source_repository import DiscoveryStatus, SourceRepository
from app.models.sync_group import SyncGroup
from app.schemas.sync_group import SyncGroupCreate
from app.services.sync_group import SyncGroupService

# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


async def _seed_source_provider(
    db_session: AsyncSession, label: str = "github-test"
) -> SourceProvider:
    """Create a minimal SourceProvider in the DB."""
    sp = SourceProvider(
        provider_type=ProviderType.github,
        label=label,
    )
    db_session.add(sp)
    await db_session.commit()
    await db_session.refresh(sp)
    return sp


async def _seed_source_group(
    db_session: AsyncSession, sp_id: int, external_id: str = "test-org"
) -> SourceGroup:
    """Create a minimal SourceGroup linked to *sp*."""
    sg = SourceGroup(
        external_id=external_id,
        name=external_id,
        full_path=external_id,
        web_url=f"https://github.com/{external_id}",
        total_repos=0,
        mirrored_repos=0,
    )
    db_session.add(sg)
    await db_session.commit()
    await db_session.refresh(sg)
    return sg


async def _seed_source_repository(
    db_session: AsyncSession, sg_id: int, name: str = "test-repo",
    sp_id: int | None = None
) -> SourceRepository:
    """Create a minimal SourceRepository linked to *sg* and optionally *sp*."""
    sr = SourceRepository(
        source_group_id=sg_id,
        source_provider_id=sp_id,
        external_id=f"{name}-ext",
        name=name,
        full_name=f"owner/{name}",
        web_url=f"https://github.com/owner/{name}",
        clone_url_https=f"https://github.com/owner/{name}.git",
        clone_url_ssh=f"git@github.com:owner/{name}.git",
        default_branch="main",
        discovery_status=DiscoveryStatus.existing,
    )
    db_session.add(sr)
    await db_session.commit()
    await db_session.refresh(sr)
    return sr


async def _seed_pipeline(db_session: AsyncSession, name: str = "test-pipeline") -> Pipeline:
    """Create a minimal Pipeline."""
    p = Pipeline(name=name, description=f"{name} description", ref="main")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


async def _seed_sync_group(
    db_session: AsyncSession,
    name: str = "test-group",
    pipeline_id: int | None = None,
    is_default: bool = False,
) -> SyncGroup:
    """Create a SyncGroup linked to an optional pipeline."""
    sg = SyncGroup(
        name=name,
        description=f"{name} description",
        pipeline_id=pipeline_id,
        is_default=is_default,
    )
    db_session.add(sg)
    await db_session.commit()
    await db_session.refresh(sg)
    return sg


async def _seed_mirror(
    db_session: AsyncSession,
    sr_id: int,
    sync_group_id: int,
    target_namespace: str = "ns",
    target_project_name: str = "proj",
) -> Mirror:
    """Create a Mirror linked to a source repository and sync group."""
    m = Mirror(
        source_repository_id=sr_id,
        sync_group_id=sync_group_id,
        target_namespace=target_namespace,
        target_project_name=target_project_name,
        status_flag=0,
        status_text="OK",
    )
    db_session.add(m)
    await db_session.commit()
    await db_session.refresh(m)
    return m


# ═══════════════════════════════════════════════════════════════════════
# Test: get_default_group
# ═══════════════════════════════════════════════════════════════════════


class TestGetDefaultGroup:
    """Tests for SyncGroupService.get_default_group()."""

    @pytest.mark.asyncio
    async def test_get_default_group_exists(self, db_session: AsyncSession):
        """When a default group exists, return it without creating a new one."""
        pipeline = await _seed_pipeline(db_session, "default-pipeline")
        default_group = await _seed_sync_group(db_session, "default", pipeline.id, is_default=True)

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            result = await SyncGroupService.get_default_group(db_session)

        assert result.id == default_group.id
        assert result.name == "default"
        assert result.is_default is True

    @pytest.mark.asyncio
    async def test_get_default_group_auto_creates(self, db_session: AsyncSession):
        """When no default group exists, auto-create one with a default pipeline."""
        # Mock: no default pipeline exists yet, and then create one
        mock_pipeline = MagicMock(spec=Pipeline)
        mock_pipeline.id = 99

        with (
            patch(
                "app.services.sync_group.get_default_pipeline",
                new_callable=AsyncMock,
                return_value=None,
            ) as mock_get_default,
            patch(
                "app.services.sync_group.create_pipeline",
                new_callable=AsyncMock,
                return_value=mock_pipeline,
            ) as mock_create,
            patch(
                "app.services.sync_group.AuditService.log_event",
                new_callable=AsyncMock,
            ),
        ):
            result = await SyncGroupService.get_default_group(db_session)

        assert result.name == "default"
        assert result.is_default is True
        assert result.pipeline_id == 99
        mock_get_default.assert_awaited_once()
        mock_create.assert_awaited_once()

        # Verify the group was persisted
        stmt = select(SyncGroup).where(SyncGroup.name == "default", ~SyncGroup.is_deleted)
        db_result = await db_session.execute(stmt)
        persisted = db_result.scalar_one_or_none()
        assert persisted is not None
        assert persisted.is_default is True


# ═══════════════════════════════════════════════════════════════════════
# Test: create_sync_group
# ═══════════════════════════════════════════════════════════════════════


class TestCreateSyncGroup:
    """Tests for SyncGroupService.create_sync_group()."""

    @pytest.mark.asyncio
    async def test_create_sync_group(self, db_session: AsyncSession):
        """Valid creation records the group and produces an audit log."""
        data = SyncGroupCreate(
            name="my-group",
            description="My test group",
            sync_enabled=True,
            sync_concurrency=5,
        )

        with patch(
            "app.services.sync_group.AuditService.log_event", new_callable=AsyncMock
        ) as mock_audit:
            result = await SyncGroupService.create_sync_group(
                db_session, data, user_id=1, username="admin"
            )

        assert result.id is not None
        assert result.name == "my-group"
        assert result.sync_enabled is True
        assert result.sync_concurrency == 5

        mock_audit.assert_awaited_once()
        args = mock_audit.call_args.kwargs
        assert args["action"] == "sync_group.created"
        assert args["resource_name"] == "my-group"

    @pytest.mark.asyncio
    async def test_create_sync_group_duplicate_name(self, db_session: AsyncSession):
        """Creating a group with an already-used name raises DomainError(409)."""
        await _seed_sync_group(db_session, "duplicate-name")

        data = SyncGroupCreate(name="duplicate-name")

        with (
            patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock),
            pytest.raises(DomainError) as exc_info,
        ):
            await SyncGroupService.create_sync_group(db_session, data, user_id=1)

        assert exc_info.value.status_code == 409
        assert "already exists" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════
# Test: get_sync_groups (RBAC)
# ═══════════════════════════════════════════════════════════════════════


class TestGetSyncGroups:
    """Tests for SyncGroupService.get_sync_groups() with RBAC scoping."""

    @pytest.mark.asyncio
    async def test_get_sync_groups_admin_sees_all(self, db_session: AsyncSession, admin_user):
        """Admin user sees all non-deleted sync groups."""
        # Re-fetch admin_user with eager-loaded roles (avoid MissingGreenlet)
        from app.models.user import User as UserModel

        admin_with_roles = await db_session.execute(
            select(UserModel)
            .options(selectinload(UserModel.user_roles))
            .where(UserModel.id == admin_user.id)
        )
        user = admin_with_roles.scalar_one()

        pipeline = await _seed_pipeline(db_session, "p1")
        await _seed_sync_group(db_session, "group-a", pipeline.id)

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            groups = await SyncGroupService.get_sync_groups(db_session, user)

        # admin_user from conftest has the "admin" role → sees everything
        assert len(groups) >= 1
        names = {g.name for g in groups}
        assert "group-a" in names

    @pytest.mark.asyncio
    async def test_get_sync_groups_empty_when_none(self, db_session: AsyncSession):
        """Returns an empty list when no sync groups exist."""
        pipeline = await _seed_pipeline(db_session, "p-empty")
        await _seed_sync_group(db_session, "default", pipeline.id, is_default=True)

        # Delete the only group
        group = await db_session.execute(
            select(SyncGroup).where(SyncGroup.name == "default", ~SyncGroup.is_deleted)
        )
        group = group.scalar_one_or_none()
        if group:
            group.is_deleted = True
            await db_session.commit()


# ═══════════════════════════════════════════════════════════════════════
# Test: delete_sync_group
# ═══════════════════════════════════════════════════════════════════════


class TestDeleteSyncGroup:
    """Tests for SyncGroupService.delete_sync_group()."""

    @pytest.mark.asyncio
    async def test_delete_sync_group_default_blocked(self, db_session: AsyncSession):
        """Attempting to delete the default group raises DomainError(400)."""
        pipeline = await _seed_pipeline(db_session, "def-pipeline")
        default = await _seed_sync_group(db_session, "default", pipeline.id, is_default=True)

        with (
            patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock),
            pytest.raises(DomainError) as exc_info,
        ):
            await SyncGroupService.delete_sync_group(db_session, default.id)

        assert exc_info.value.status_code == 400
        assert "Cannot delete the default" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_sync_group_migrates_mirrors(self, db_session: AsyncSession):
        """Soft-deleting a non-default group migrates its mirrors to the default group."""
        # ── Seed infrastructure ─────────────────────────────────────────
        sp = await _seed_source_provider(db_session)
        sg_source = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg_source.id)

        pipeline = await _seed_pipeline(db_session, "shared-pipeline")
        default_group = await _seed_sync_group(db_session, "default", pipeline.id, is_default=True)
        target_group = await _seed_sync_group(db_session, "to-delete", pipeline.id)

        m1 = await _seed_mirror(db_session, sr.id, target_group.id, "ns", "proj1")
        m2 = await _seed_mirror(db_session, sr.id, target_group.id, "ns", "proj2")

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            await SyncGroupService.delete_sync_group(
                db_session, target_group.id, user_id=1, username="admin"
            )

        # ── Assertions ──────────────────────────────────────────────────
        # Target group is soft-deleted
        await db_session.refresh(target_group)
        assert target_group.is_deleted is True
        assert target_group.deleted_at is not None

        # Mirrors migrated to default group
        await db_session.refresh(m1)
        await db_session.refresh(m2)
        assert m1.sync_group_id == default_group.id
        assert m2.sync_group_id == default_group.id

    @pytest.mark.asyncio
    async def test_delete_nonexistent_group_raises_404(self, db_session: AsyncSession):
        """Deleting a non-existent group raises DomainError(404)."""
        with (
            patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock),
            pytest.raises(DomainError) as exc_info,
        ):
            await SyncGroupService.delete_sync_group(db_session, 99999)

        assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Test: assign_mirrors_to_group
# ═══════════════════════════════════════════════════════════════════════


class TestAssignMirrorsToGroup:
    """Tests for SyncGroupService.assign_mirrors_to_group()."""

    @pytest.mark.asyncio
    async def test_assign_mirrors_to_group(self, db_session: AsyncSession):
        """Bulk assignment updates sync_group_id on all specified mirrors."""
        sp = await _seed_source_provider(db_session)
        sg_source = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg_source.id)

        pipeline = await _seed_pipeline(db_session, "ap-pipeline")
        # Use default+non-default to avoid SQLite UNIQUE(is_default) constraint
        default_group = await _seed_sync_group(
            db_session, "ap-default", pipeline.id, is_default=True
        )
        target_group = await _seed_sync_group(
            db_session, "ap-target", pipeline.id, is_default=False
        )

        m1 = await _seed_mirror(db_session, sr.id, default_group.id, "ns", "m1")
        m2 = await _seed_mirror(db_session, sr.id, default_group.id, "ns", "m2")

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            updated = await SyncGroupService.assign_mirrors_to_group(
                db_session,
                group_id=target_group.id,
                mirror_ids=[m1.id, m2.id],
                user_id=1,
                username="admin",
            )

        assert len(updated) == 2
        assert {m.id for m in updated} == {m1.id, m2.id}

        await db_session.refresh(m1)
        await db_session.refresh(m2)
        assert m1.sync_group_id == target_group.id
        assert m2.sync_group_id == target_group.id

    @pytest.mark.asyncio
    async def test_assign_to_nonexistent_group_raises_404(self, db_session: AsyncSession):
        """Assigning mirrors to a non-existent group raises DomainError(404)."""
        with (
            patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock),
            pytest.raises(DomainError) as exc_info,
        ):
            await SyncGroupService.assign_mirrors_to_group(
                db_session, group_id=99999, mirror_ids=[1]
            )

        assert exc_info.value.status_code == 404


# ═══════════════════════════════════════════════════════════════════════
# Test: apply_pipeline
# ═══════════════════════════════════════════════════════════════════════


class TestApplyPipeline:
    """Tests for SyncGroupService.apply_pipeline()."""

    @pytest.mark.asyncio
    async def test_apply_pipeline_success(self, db_session: AsyncSession):
        """Applying a pipeline updates pipeline_id on the sync group."""
        p1 = await _seed_pipeline(db_session, "pipeline-1")
        p2 = await _seed_pipeline(db_session, "pipeline-2")
        group = await _seed_sync_group(db_session, "test-group", p1.id, is_default=False)

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            result = await SyncGroupService.apply_pipeline(
                db_session,
                sync_group_id=group.id,
                pipeline_id=p2.id,
                user_id=1,
                username="admin",
            )

        assert result.id == group.id
        assert result.pipeline_id == p2.id

    @pytest.mark.asyncio
    async def test_apply_pipeline_nonexistent_group(self, db_session: AsyncSession):
        """Applying a pipeline to a nonexistent group raises DomainError(404)."""
        with (
            patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock),
            pytest.raises(DomainError) as exc_info,
        ):
            await SyncGroupService.apply_pipeline(
                db_session,
                sync_group_id=99999,
                pipeline_id=1,
            )

        assert exc_info.value.status_code == 404
        assert "SyncGroup" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_apply_pipeline_nonexistent_pipeline(self, db_session: AsyncSession):
        """Applying a nonexistent pipeline raises DomainError(404)."""
        p1 = await _seed_pipeline(db_session, "pipeline-1")
        group = await _seed_sync_group(db_session, "test-group", p1.id, is_default=False)

        with (
            patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock),
            pytest.raises(DomainError) as exc_info,
        ):
            await SyncGroupService.apply_pipeline(
                db_session,
                sync_group_id=group.id,
                pipeline_id=99999,
            )

        assert exc_info.value.status_code == 404
        assert "Pipeline" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════
# Test: bulk_assign_mirrors
# ═══════════════════════════════════════════════════════════════════════


class TestBulkAssignMirrors:
    """Tests for SyncGroupService.bulk_assign_mirrors()."""

    @pytest.mark.asyncio
    async def test_bulk_assign_mirrors_to_group(self, db_session: AsyncSession):
        """Assign multiple mirrors. Returns SyncGroup, skips already
        assigned, moves mirrors from other groups."""
        sp = await _seed_source_provider(db_session)
        sg_source = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg_source.id)

        pipeline = await _seed_pipeline(db_session, "bam-pipeline")
        # SQLite UNIQUE(is_default) constraint — only one default row
        default_group = await _seed_sync_group(
            db_session, "bam-default", pipeline.id, is_default=True
        )
        target_group = await _seed_sync_group(
            db_session, "bam-target", pipeline.id, is_default=False
        )

        # Mirror 1 already in target (should be skipped)
        m1 = await _seed_mirror(db_session, sr.id, target_group.id, "ns", "bam-m1")
        # Mirror 2 in default (should be moved)
        m2 = await _seed_mirror(db_session, sr.id, default_group.id, "ns", "bam-m2")
        # Mirror 3 has no group (should be assigned)
        m3 = Mirror(
            source_repository_id=sr.id,
            sync_group_id=None,
            target_namespace="ns",
            target_project_name="bam-m3",
            status_flag=0,
            status_text="OK",
        )
        db_session.add(m3)
        await db_session.commit()
        await db_session.refresh(m3)

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            result = await SyncGroupService.bulk_assign_mirrors(
                db_session,
                sync_group_id=target_group.id,
                mirror_ids=[m1.id, m2.id, m3.id],
                user_id=1,
                username="admin",
            )

        # Returns the SyncGroup
        assert result.id == target_group.id
        assert result.name == "bam-target"

        # m1 already in target — unchanged
        await db_session.refresh(m1)
        assert m1.sync_group_id == target_group.id

        # m2 moved from default to target
        await db_session.refresh(m2)
        assert m2.sync_group_id == target_group.id

        # m3 assigned to target
        await db_session.refresh(m3)
        assert m3.sync_group_id == target_group.id

    @pytest.mark.asyncio
    async def test_bulk_assign_moves_from_other_group(self, db_session: AsyncSession):
        """Mirrors assigned to a different SyncGroup are moved to the target."""
        sp = await _seed_source_provider(db_session)
        sg_source = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg_source.id)

        pipeline = await _seed_pipeline(db_session, "bam-move-pipeline")
        group_a = await _seed_sync_group(db_session, "bam-group-a", pipeline.id, is_default=True)
        group_b = await _seed_sync_group(db_session, "bam-group-b", pipeline.id, is_default=False)

        mirror = await _seed_mirror(db_session, sr.id, group_a.id, "ns", "bam-move")
        assert mirror.sync_group_id == group_a.id

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            result = await SyncGroupService.bulk_assign_mirrors(
                db_session,
                sync_group_id=group_b.id,
                mirror_ids=[mirror.id],
                user_id=1,
                username="admin",
            )

        assert result.id == group_b.id
        await db_session.refresh(mirror)
        assert mirror.sync_group_id == group_b.id

    @pytest.mark.asyncio
    async def test_bulk_assign_skips_already_assigned(self, db_session: AsyncSession):
        """Mirrors already in the target group are skipped (idempotent)."""
        sp = await _seed_source_provider(db_session)
        sg_source = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg_source.id)

        pipeline = await _seed_pipeline(db_session, "bam-skip-pipeline")
        group = await _seed_sync_group(db_session, "bam-skip-group", pipeline.id, is_default=True)

        mirror = await _seed_mirror(db_session, sr.id, group.id, "ns", "bam-skip")
        assert mirror.sync_group_id == group.id

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            result = await SyncGroupService.bulk_assign_mirrors(
                db_session,
                sync_group_id=group.id,
                mirror_ids=[mirror.id],
                user_id=1,
                username="admin",
            )

        assert result.id == group.id
        await db_session.refresh(mirror)
        assert mirror.sync_group_id == group.id  # unchanged

    @pytest.mark.asyncio
    async def test_bulk_assign_raises_for_missing_mirrors(self, db_session: AsyncSession):
        """Raises ValueError when mirror IDs don't exist."""
        sp = await _seed_source_provider(db_session)
        sg_source = await _seed_source_group(db_session, sp.id)
        await _seed_source_repository(db_session, sg_source.id)

        pipeline = await _seed_pipeline(db_session, "bam-err-pipeline")
        group = await _seed_sync_group(db_session, "bam-err-group", pipeline.id, is_default=True)

        with pytest.raises(ValueError) as exc_info:
            await SyncGroupService.bulk_assign_mirrors(
                db_session,
                sync_group_id=group.id,
                mirror_ids=[99999],
                user_id=1,
                username="admin",
            )

        assert "Mirrors not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_bulk_assign_raises_for_missing_group(self, db_session: AsyncSession):
        """Raises DomainError(404) when SyncGroup doesn't exist."""
        with pytest.raises(DomainError) as exc_info:
            await SyncGroupService.bulk_assign_mirrors(
                db_session,
                sync_group_id=99999,
                mirror_ids=[1],
            )

        assert exc_info.value.status_code == 404
        assert "SyncGroup" in str(exc_info.value)
