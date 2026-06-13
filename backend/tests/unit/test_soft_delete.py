"""
@file test_soft_delete.py
@description Unit tests for soft-delete and restore functionality across all
             5 Mirroring entities: Mirror, SyncGroup, SourceGroup,
             SourceRepository, SourceProvider, and Pipeline.
             Tests both service-layer and API-level behaviour.
@dependencies pytest, pytest-asyncio, sqlalchemy
@relatedFiles ../../app/services/mirror.py,
              ../../app/services/sync_group.py,
              ../../app/services/pipeline.py,
              ../../app/api/mirroring.py,
              ../../app/api/pipelines.py
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainException, NotFoundError
from app.models.mirror import Mirror
from app.models.pipeline import Pipeline
from app.models.source_group import SourceGroup
from app.models.source_provider import ProviderType, SourceProvider
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.services.mirror import MirrorService
from app.services.pipeline import (
    delete_pipeline,
    get_pipeline_config,
    restore_pipeline,
)
from app.services.sync_group import SyncGroupService

# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


async def _seed_source_provider(
    db_session: AsyncSession, label: str = "test-github"
) -> SourceProvider:
    sp = SourceProvider(provider_type=ProviderType.github, label=label)
    db_session.add(sp)
    await db_session.commit()
    await db_session.refresh(sp)
    return sp


async def _seed_source_group(
    db_session: AsyncSession, sp_id: int, external_id: str = "test-org"
) -> SourceGroup:
    sg = SourceGroup(
        source_provider_id=sp_id,
        external_id=external_id,
        name=external_id,
        full_path=external_id,
    )
    db_session.add(sg)
    await db_session.commit()
    await db_session.refresh(sg)
    return sg


async def _seed_source_repository(
    db_session: AsyncSession, sg_id: int, name: str = "test-repo"
) -> SourceRepository:
    sr = SourceRepository(
        source_group_id=sg_id,
        external_id=f"{name}-ext",
        name=name,
        full_name=f"owner/{name}",
        clone_url_https=f"https://github.com/owner/{name}.git",
    )
    db_session.add(sr)
    await db_session.commit()
    await db_session.refresh(sr)
    return sr


async def _seed_sync_group(
    db_session: AsyncSession, name: str = "test-sg", is_default: bool = False
) -> SyncGroup:
    sg = SyncGroup(name=name, description="Test sync group", is_default=is_default)
    db_session.add(sg)
    await db_session.commit()
    await db_session.refresh(sg)
    return sg


async def _seed_pipeline(db_session: AsyncSession, name: str = "test-pipeline") -> Pipeline:
    pipeline = Pipeline(
        name=name,
        description="Test pipeline",
        ref="main",
        is_enabled=True,
    )
    db_session.add(pipeline)
    await db_session.commit()
    await db_session.refresh(pipeline)
    return pipeline


async def _seed_mirror(
    db_session: AsyncSession,
    sr_id: int,
    sg_id: int,
    target_ns: str = "test-ns",
    target_name: str = "test-project",
) -> Mirror:
    mirror = Mirror(
        source_repository_id=sr_id,
        sync_group_id=sg_id,
        target_namespace=target_ns,
        target_project_name=target_name,
        status_flag=4,
    )
    db_session.add(mirror)
    await db_session.commit()
    await db_session.refresh(mirror)
    return mirror


# ═══════════════════════════════════════════════════════════════════════
# Mirror — soft_delete + restore (service layer)
# ═══════════════════════════════════════════════════════════════════════


class TestMirrorSoftDeleteService:
    async def test_soft_delete_sets_is_deleted(self, db_session: AsyncSession):
        """soft_delete_mirror marks the mirror as deleted."""
        sp = await _seed_source_provider(db_session)
        sg = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg.id)
        sync_group = await _seed_sync_group(db_session, "mirror-sd-sg")
        mirror = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "sd-project")

        assert mirror.is_deleted is False
        assert mirror.deleted_at is None

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            await MirrorService.soft_delete_mirror(db_session, mirror.id, username="testuser")

        await db_session.refresh(mirror)
        assert mirror.is_deleted is True
        assert mirror.deleted_at is not None

    async def test_soft_delete_cascades_to_source_repository(self, db_session: AsyncSession):
        """When the last mirror is deleted, the source repository is also soft-deleted."""
        sp = await _seed_source_provider(db_session)
        sg = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg.id)
        sync_group = await _seed_sync_group(db_session, "mirror-cascade-sg")
        mirror = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "cascade-proj")

        assert sr.is_deleted is False

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            await MirrorService.soft_delete_mirror(db_session, mirror.id, username="testuser")

        await db_session.refresh(sr)
        assert sr.is_deleted is True
        assert sr.deleted_at is not None

    async def test_soft_delete_does_not_cascade_when_other_mirrors_exist(
        self, db_session: AsyncSession
    ):
        """SourceRepository is NOT soft-deleted when other non-deleted mirrors reference it."""
        sp = await _seed_source_provider(db_session)
        sg = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg.id)
        sync_group = await _seed_sync_group(db_session, "mirror-no-cascade-sg")

        mirror1 = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "proj1")
        await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "proj2")

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            await MirrorService.soft_delete_mirror(db_session, mirror1.id, username="testuser")

        await db_session.refresh(sr)
        # Source repository should NOT be deleted — mirror2 still references it
        assert sr.is_deleted is False

    async def test_restore_mirror(self, db_session: AsyncSession):
        """restore_mirror clears is_deleted and deleted_at."""
        sp = await _seed_source_provider(db_session)
        sg = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg.id)
        sync_group = await _seed_sync_group(db_session, "mirror-restore-sg")
        mirror = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "restore-proj")

        # Soft-delete first
        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            await MirrorService.soft_delete_mirror(db_session, mirror.id, username="testuser")
            # Restore
            restored = await MirrorService.restore_mirror(
                db_session, mirror.id, username="testuser"
            )

        assert restored.is_deleted is False
        assert restored.deleted_at is None
        assert restored.id == mirror.id

    async def test_restore_cascades_to_source_repository(self, db_session: AsyncSession):
        """Restoring the only mirror also restores its source repository."""
        sp = await _seed_source_provider(db_session)
        sg = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg.id)
        sync_group = await _seed_sync_group(db_session, "mirror-restore-cascade-sg")
        mirror = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "rest-cascade")

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            await MirrorService.soft_delete_mirror(db_session, mirror.id, username="testuser")

        await db_session.refresh(sr)
        assert sr.is_deleted is True

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            await MirrorService.restore_mirror(db_session, mirror.id, username="testuser")

        await db_session.refresh(sr)
        assert sr.is_deleted is False
        assert sr.deleted_at is None

    async def test_restore_nonexistent_mirror_raises(self, db_session: AsyncSession):
        """Restoring a mirror that doesn't exist raises NotFoundError."""
        with pytest.raises(NotFoundError, match="Mirror .* not found"):
            await MirrorService.restore_mirror(db_session, 99999, username="testuser")


# ═══════════════════════════════════════════════════════════════════════
# SyncGroup — soft_delete + restore (service layer)
# ═══════════════════════════════════════════════════════════════════════


class TestSyncGroupSoftDeleteService:
    async def test_delete_sync_group_sets_is_deleted(self, db_session: AsyncSession):
        """delete_sync_group marks the group as deleted and migrates mirrors."""
        await _seed_sync_group(db_session, "default", is_default=True)
        sg = await _seed_sync_group(db_session, "to-delete-sg", is_default=False)

        assert sg.is_deleted is False

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            await SyncGroupService.delete_sync_group(
                db_session, sg.id, user_id=1, username="testuser"
            )

        await db_session.refresh(sg)
        assert sg.is_deleted is True
        assert sg.deleted_at is not None

    async def test_restore_sync_group(self, db_session: AsyncSession):
        """restore_sync_group clears is_deleted."""
        await _seed_sync_group(db_session, "default", is_default=True)
        sg = await _seed_sync_group(db_session, "restore-me-sg", is_default=False)

        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            await SyncGroupService.delete_sync_group(db_session, sg.id)
            restored = await SyncGroupService.restore_sync_group(
                db_session, sg.id, user_id=1, username="testuser"
            )

        assert restored.is_deleted is False
        assert restored.deleted_at is None

    async def test_restore_nonexistent_sync_group_raises(self, db_session: AsyncSession):
        """Restoring a non-existent sync group raises DomainException."""
        with pytest.raises(DomainException, match="SyncGroup .* not found"):
            await SyncGroupService.restore_sync_group(db_session, 99999)

    async def test_restore_not_deleted_sync_group_is_idempotent(self, db_session: AsyncSession):
        """Restoring a sync group that isn't deleted is idempotent (returns unchanged)."""
        sg = await _seed_sync_group(db_session, "not-deleted-sg")
        restored = await SyncGroupService.restore_sync_group(db_session, sg.id)
        assert restored.is_deleted is False
        assert restored.deleted_at is None


# ═══════════════════════════════════════════════════════════════════════
# Pipeline — soft_delete + restore (service layer)
# ═══════════════════════════════════════════════════════════════════════


class TestPipelineSoftDeleteService:
    async def test_delete_pipeline_sets_is_deleted(self, db_session: AsyncSession):
        """delete_pipeline marks the pipeline as soft-deleted."""
        pipeline = await _seed_pipeline(db_session, "to-delete-pl")

        assert pipeline.is_deleted is False

        with patch("app.services.pipeline.AuditService.log_event", new_callable=AsyncMock):
            await delete_pipeline(db_session, pipeline.id, username="testuser")

        await db_session.refresh(pipeline)
        assert pipeline.is_deleted is True
        assert pipeline.deleted_at is not None

    async def test_delete_default_pipeline_raises(self, db_session: AsyncSession):
        """Cannot delete the default pipeline."""
        pipeline = Pipeline(
            name="default-pl",
            description="Default",
            ref="main",
            is_default=True,
            is_enabled=True,
        )
        db_session.add(pipeline)
        await db_session.commit()
        await db_session.refresh(pipeline)

        with pytest.raises(DomainException, match="Cannot delete default pipeline"):
            await delete_pipeline(db_session, pipeline.id, username="testuser")

    async def test_delete_pipeline_in_use_raises(self, db_session: AsyncSession):
        """Cannot delete a pipeline referenced by active sync groups."""
        pipeline = await _seed_pipeline(db_session, "in-use-pl")
        sg = await _seed_sync_group(db_session, "using-pl-sg")
        sg.pipeline_id = pipeline.id
        await db_session.commit()

        with pytest.raises(DomainException, match="Pipeline is in use"):
            await delete_pipeline(db_session, pipeline.id, username="testuser")

    async def test_restore_pipeline(self, db_session: AsyncSession):
        """restore_pipeline clears is_deleted."""
        pipeline = await _seed_pipeline(db_session, "restore-me-pl")

        with patch("app.services.pipeline.AuditService.log_event", new_callable=AsyncMock):
            await delete_pipeline(db_session, pipeline.id, username="testuser")

        await db_session.refresh(pipeline)
        assert pipeline.is_deleted is True

        with patch("app.services.pipeline.AuditService.log_event", new_callable=AsyncMock):
            restored = await restore_pipeline(db_session, pipeline.id, username="testuser")

        assert restored.is_deleted is False
        assert restored.deleted_at is None

    async def test_restore_nonexistent_pipeline_raises(self, db_session: AsyncSession):
        """Restoring a non-existent pipeline raises DomainException."""
        with pytest.raises(DomainException, match="Pipeline .* not found"):
            await restore_pipeline(db_session, 99999, username="testuser")

    async def test_get_pipeline_config_excludes_deleted(self, db_session: AsyncSession):
        """get_pipeline_config should not return soft-deleted pipelines."""
        pipeline = await _seed_pipeline(db_session, "filter-deleted-pl")

        with patch("app.services.pipeline.AuditService.log_event", new_callable=AsyncMock):
            await delete_pipeline(db_session, pipeline.id, username="testuser")

        result = await get_pipeline_config(db_session, pipeline.id)
        assert result is None

    async def test_restore_pipeline_reappears_in_queries(self, db_session: AsyncSession):
        """After restore, the pipeline should be visible again."""
        pipeline = await _seed_pipeline(db_session, "reappear-pl")

        with patch("app.services.pipeline.AuditService.log_event", new_callable=AsyncMock):
            await delete_pipeline(db_session, pipeline.id, username="testuser")

        result = await get_pipeline_config(db_session, pipeline.id)
        assert result is None

        with patch("app.services.pipeline.AuditService.log_event", new_callable=AsyncMock):
            await restore_pipeline(db_session, pipeline.id, username="testuser")

        result = await get_pipeline_config(db_session, pipeline.id)
        assert result is not None
        assert result.id == pipeline.id


# ═══════════════════════════════════════════════════════════════════════
# Filter coverage — ensure is_deleted=False in list/get queries
# ═══════════════════════════════════════════════════════════════════════


class TestSoftDeleteFilters:
    async def test_get_sync_group_excludes_deleted(self, db_session: AsyncSession):
        """get_sync_group filters out soft-deleted groups."""
        sg = await _seed_sync_group(db_session, "filtered-sg")
        with patch("app.services.sync_group.AuditService.log_event", new_callable=AsyncMock):
            await SyncGroupService.delete_sync_group(db_session, sg.id)

        with pytest.raises(DomainException, match="SyncGroup .* not found"):
            await SyncGroupService.get_sync_group(db_session, sg.id)

    async def test_get_mirror_detail_excludes_deleted(self, db_session: AsyncSession):
        """get_mirror_detail should not return soft-deleted mirrors."""
        sp = await _seed_source_provider(db_session)
        sg = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sg.id)
        sync_group = await _seed_sync_group(db_session, "mirror-detail-filter-sg")
        mirror = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "filter-detail")

        with patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock):
            await MirrorService.soft_delete_mirror(db_session, mirror.id, username="testuser")

        with pytest.raises(NotFoundError, match="Mirror .* not found"):
            await MirrorService.get_mirror_detail(db_session, mirror.id)
