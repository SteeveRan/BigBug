"""
@file test_cleanup.py
@description Unit tests for CleanupService — physical deletion of soft-deleted
             Mirroring entities past retention period.
@dependencies pytest, pytest-asyncio, sqlalchemy, app.services.cleanup
@relatedFiles ../../app/services/cleanup.py,
              ../../app/models/mirror.py,
              ../../app/models/mirror_log.py,
              ../../app/models/sync_group.py,
              ../../app/models/source_repository.py,
              ../../app/models/source_group.py,
              ../../app/models/pipeline.py
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mirror import Mirror
from app.models.mirror_log import MirrorLog, MirrorLogType
from app.models.pipeline import Pipeline
from app.models.source_group import SourceGroup
from app.models.source_provider import ProviderType, SourceProvider
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.services.cleanup import CleanupResult, CleanupService

# Helpers re-used from test_soft_delete.py pattern
# (re-defining locally to avoid import-time coupling)


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
    sync_group_id: int,
    target_ns: str = "test-ns",
    target_name: str = "test-project",
) -> Mirror:
    mirror = Mirror(
        source_repository_id=sr_id,
        sync_group_id=sync_group_id,
        target_namespace=target_ns,
        target_project_name=target_name,
        status_flag=4,
    )
    db_session.add(mirror)
    await db_session.commit()
    await db_session.refresh(mirror)
    return mirror


async def _seed_mirror_log(
    db_session: AsyncSession,
    mirror_id: int,
    log_type: MirrorLogType = MirrorLogType.sync,
) -> MirrorLog:
    log_entry = MirrorLog(
        mirror_id=mirror_id,
        log_type=log_type,
        status_flag=0,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.add(log_entry)
    await db_session.commit()
    await db_session.refresh(log_entry)
    return log_entry


def _make_cutoff(days_ago: int = 31) -> datetime:
    """Return a ``deleted_at`` value *before* the default 30-day retention."""
    return datetime.now(UTC) - timedelta(days=days_ago)


class TestCleanupRemovesOldRecords:
    """Records with deleted_at older than retention are physically removed."""

    async def test_deletes_old_soft_deleted_mirror(self, db_session: AsyncSession):
        """A mirror soft-deleted > retention_days ago is physically deleted."""
        sp = await _seed_source_provider(db_session)
        sgroup = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sgroup.id)
        sync_group = await _seed_sync_group(db_session, "cleanup-old-mirror-sg")
        mirror = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "old-mirror")

        # Soft-delete the mirror with an old timestamp
        mirror.is_deleted = True
        mirror.deleted_at = _make_cutoff(31)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.mirrors_deleted == 1
        assert result.total_deleted >= 1

        # Verify mirror is gone
        from sqlalchemy import select

        check = await db_session.execute(select(Mirror).where(Mirror.id == mirror.id))
        assert check.scalar_one_or_none() is None

    async def test_deletes_old_soft_deleted_pipeline(self, db_session: AsyncSession):
        """A pipeline soft-deleted > retention_days ago is physically deleted."""
        pipeline = await _seed_pipeline(db_session, "cleanup-old-pipeline")

        pipeline.is_deleted = True
        pipeline.deleted_at = _make_cutoff(31)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.pipelines_deleted == 1

        from sqlalchemy import select

        check = await db_session.execute(select(Pipeline).where(Pipeline.id == pipeline.id))
        assert check.scalar_one_or_none() is None

    async def test_deletes_old_soft_deleted_source_group(self, db_session: AsyncSession):
        """A source group soft-deleted > retention_days ago (with no repos) is removed."""
        sp = await _seed_source_provider(db_session)
        sgroup = await _seed_source_group(db_session, sp.id, "cleanup-old-sourcegroup")

        sgroup.is_deleted = True
        sgroup.deleted_at = _make_cutoff(31)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.source_groups_deleted == 1

        from sqlalchemy import select

        check = await db_session.execute(select(SourceGroup).where(SourceGroup.id == sgroup.id))
        assert check.scalar_one_or_none() is None


class TestCleanupPreservesRecentRecords:
    """Records with deleted_at younger than retention are NOT removed."""

    async def test_preserves_recent_soft_deleted_mirror(self, db_session: AsyncSession):
        """A mirror deleted 5 days ago stays."""
        sp = await _seed_source_provider(db_session)
        sgroup = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sgroup.id)
        sync_group = await _seed_sync_group(db_session, "cleanup-recent-mirror-sg")
        mirror = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "recent-mirror")

        mirror.is_deleted = True
        mirror.deleted_at = _make_cutoff(5)  # 5 days ago — within retention
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.mirrors_deleted == 0

        from sqlalchemy import select

        check = await db_session.execute(select(Mirror).where(Mirror.id == mirror.id))
        assert check.scalar_one_or_none() is not None

    async def test_preserves_recent_soft_deleted_pipeline(self, db_session: AsyncSession):
        """A pipeline deleted 1 day ago stays."""
        pipeline = await _seed_pipeline(db_session, "cleanup-recent-pipeline")

        pipeline.is_deleted = True
        pipeline.deleted_at = _make_cutoff(1)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.pipelines_deleted == 0

        from sqlalchemy import select

        check = await db_session.execute(select(Pipeline).where(Pipeline.id == pipeline.id))
        assert check.scalar_one_or_none() is not None


class TestCleanupCascade:
    """Cascade deletion: Mirror → MirrorLog, SourceRepository when no active mirrors."""

    async def test_deletes_mirror_and_its_logs(self, db_session: AsyncSession):
        """When a mirror is physically deleted, its MirrorLogs are cascade-deleted."""
        sp = await _seed_source_provider(db_session)
        sgroup = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sgroup.id)
        sync_group = await _seed_sync_group(db_session, "cleanup-cascade-sg")
        mirror = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "cascade-mirror")
        log1 = await _seed_mirror_log(db_session, mirror.id)
        log2 = await _seed_mirror_log(db_session, mirror.id, MirrorLogType.freshness)

        mirror.is_deleted = True
        mirror.deleted_at = _make_cutoff(31)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        # MirrorLogs are cleaned by the pre-pass, Mirror is cleaned after
        assert result.mirror_logs_deleted >= 2
        assert result.mirrors_deleted == 1

        from sqlalchemy import select

        check_mirror = await db_session.execute(select(Mirror).where(Mirror.id == mirror.id))
        assert check_mirror.scalar_one_or_none() is None

        check_log1 = await db_session.execute(select(MirrorLog).where(MirrorLog.id == log1.id))
        assert check_log1.scalar_one_or_none() is None

        check_log2 = await db_session.execute(select(MirrorLog).where(MirrorLog.id == log2.id))
        assert check_log2.scalar_one_or_none() is None

    async def test_deletes_source_repository_when_all_mirrors_removed(
        self, db_session: AsyncSession
    ):
        """SourceRepository is physically deleted when all mirrors are gone."""
        sp = await _seed_source_provider(db_session)
        sgroup = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sgroup.id)

        # Soft-delete the source repo
        sr.is_deleted = True
        sr.deleted_at = _make_cutoff(31)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.source_repositories_deleted == 1

        from sqlalchemy import select

        check = await db_session.execute(
            select(SourceRepository).where(SourceRepository.id == sr.id)
        )
        assert check.scalar_one_or_none() is None


class TestCleanupPreservesActive:
    """Entities with active children are NOT deleted."""

    async def test_keeps_sync_group_when_active_mirrors_exist(self, db_session: AsyncSession):
        """A soft-deleted SyncGroup with active mirrors is NOT physically deleted."""
        sp = await _seed_source_provider(db_session)
        sgroup = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sgroup.id)
        sync_group = await _seed_sync_group(db_session, "keep-sg-active")

        # Create an active (non-deleted) mirror — presence keeps the sync group alive
        await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "active-mirror")

        # Soft-delete the sync group
        sync_group.is_deleted = True
        sync_group.deleted_at = _make_cutoff(31)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.sync_groups_deleted == 0

        from sqlalchemy import select

        check = await db_session.execute(select(SyncGroup).where(SyncGroup.id == sync_group.id))
        assert check.scalar_one_or_none() is not None

    async def test_deletes_sync_group_when_all_mirrors_are_soft_deleted(
        self, db_session: AsyncSession
    ):
        """A soft-deleted SyncGroup whose all mirrors are also soft-deleted is removed."""
        sp = await _seed_source_provider(db_session)
        sgroup = await _seed_source_group(db_session, sp.id)
        sr = await _seed_source_repository(db_session, sgroup.id)
        sync_group = await _seed_sync_group(db_session, "delete-sg-no-active")

        # Create a mirror — but also soft-delete it
        mirror = await _seed_mirror(db_session, sr.id, sync_group.id, "ns", "also-deleted-mirror")
        mirror.is_deleted = True
        mirror.deleted_at = _make_cutoff(31)

        # Soft-delete the sync group
        sync_group.is_deleted = True
        sync_group.deleted_at = _make_cutoff(31)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.sync_groups_deleted == 1
        assert result.mirrors_deleted == 1

        from sqlalchemy import select

        check_sg = await db_session.execute(select(SyncGroup).where(SyncGroup.id == sync_group.id))
        assert check_sg.scalar_one_or_none() is None

    async def test_keeps_pipeline_when_active_sync_groups_exist(self, db_session: AsyncSession):
        """A soft-deleted Pipeline with non-deleted sync groups is NOT removed."""
        pipeline = await _seed_pipeline(db_session, "keep-pl-active")
        sync_group = await _seed_sync_group(db_session, "active-sg-for-pl")
        sync_group.pipeline_id = pipeline.id
        await db_session.commit()

        pipeline.is_deleted = True
        pipeline.deleted_at = _make_cutoff(31)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.pipelines_deleted == 0

        from sqlalchemy import select

        check = await db_session.execute(select(Pipeline).where(Pipeline.id == pipeline.id))
        assert check.scalar_one_or_none() is not None


class TestCleanupResult:
    """CleanupResult returns accurate counts."""

    async def test_result_counts_are_correct(self, db_session: AsyncSession):
        """Result reflects the number of each entity type deleted."""
        # Create 2 old soft-deleted pipelines
        pl1 = await _seed_pipeline(db_session, "result-pl-1")
        pl1.is_deleted = True
        pl1.deleted_at = _make_cutoff(31)

        pl2 = await _seed_pipeline(db_session, "result-pl-2")
        pl2.is_deleted = True
        pl2.deleted_at = _make_cutoff(35)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)

        assert result.pipelines_deleted == 2
        assert result.mirrors_deleted == 0
        assert result.sync_groups_deleted == 0
        assert result.source_repositories_deleted == 0
        assert result.source_groups_deleted == 0
        assert result.mirror_logs_deleted == 0
        assert result.total_deleted == 2

    async def test_to_dict_returns_all_fields(self, db_session: AsyncSession):
        """to_dict() includes all entity types and total."""
        pipeline = await _seed_pipeline(db_session, "dict-pl")
        pipeline.is_deleted = True
        pipeline.deleted_at = _make_cutoff(31)
        await db_session.commit()

        result = await CleanupService.run_cleanup(db_session)
        d = result.to_dict()

        assert d["pipelines_deleted"] == 1
        assert d["mirrors_deleted"] == 0
        assert d["sync_groups_deleted"] == 0
        assert d["source_repositories_deleted"] == 0
        assert d["source_groups_deleted"] == 0
        assert d["mirror_logs_deleted"] == 0
        assert d["total_deleted"] == 1


class TestCleanupResultDataclass:
    """CleanupResult dataclass properties."""

    def test_initial_counts_are_zero(self):
        result = CleanupResult()
        assert result.total_deleted == 0

    def test_total_deleted_sums_all_fields(self):
        result = CleanupResult(
            mirror_logs_deleted=1,
            mirrors_deleted=2,
            sync_groups_deleted=3,
            source_repositories_deleted=4,
            source_groups_deleted=5,
            pipelines_deleted=6,
        )
        assert result.total_deleted == 21
