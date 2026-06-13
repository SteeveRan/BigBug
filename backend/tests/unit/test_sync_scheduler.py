"""
@file test_sync_scheduler.py
@description Unit tests for SyncScheduler — job scheduling, removal, error handling,
             concurrency control, and invalid cron validation.
@dependencies pytest, pytest-asyncio, unittest.mock, apscheduler
@relatedFiles ../../app/services/sync_scheduler.py, ../../app/services/mirror.py,
              ../../app/services/sync_group.py
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_group import SyncGroup
from app.services.sync_scheduler import SyncScheduler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_group(
    id_: int,
    *,
    sync_enabled: bool = True,
    sync_cron: str = "*/30 * * * *",
    sync_concurrency: int = 5,
    freshness_enabled: bool = True,
    freshness_cron: str = "0 */6 * * *",
    freshness_concurrency: int = 3,
) -> SyncGroup:
    """Create a SyncGroup instance (not persisted)."""
    sg = MagicMock(spec=SyncGroup)
    sg.id = id_
    sg.name = f"test-group-{id_}"
    sg.sync_enabled = sync_enabled
    sg.sync_cron = sync_cron
    sg.sync_concurrency = sync_concurrency
    sg.freshness_enabled = freshness_enabled
    sg.freshness_cron = freshness_cron
    sg.freshness_concurrency = freshness_concurrency
    return sg


def _mock_session_factory():
    """Return a mock session_factory."""
    mock_db = AsyncMock(spec=AsyncSession)
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = mock_db
    factory.return_value.__aexit__.return_value = None
    return factory, mock_db


# ---------------------------------------------------------------------------
# Test schedule_sync_job / schedule_freshness_job
# ---------------------------------------------------------------------------


class TestScheduleJobs:
    """Tests for scheduling individual sync and freshness jobs."""

    def test_schedule_sync_job_creates_apscheduler_job(self):
        """schedule_sync_job adds a job to the APScheduler instance."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)
        # Manually set the APScheduler mock
        scheduler._scheduler = MagicMock()

        async def _run():
            await scheduler.schedule_sync_job(1, "*/30 * * * *", 5)

        asyncio.run(_run())

        scheduler._scheduler.add_job.assert_called_once()
        call_args = scheduler._scheduler.add_job.call_args
        assert call_args.kwargs["id"] == "sync_group_1"
        assert call_args.kwargs["replace_existing"] is True
        assert call_args.kwargs["args"] == [1, 5]
        assert 1 in scheduler._sync_jobs

    def test_schedule_freshness_job_creates_apscheduler_job(self):
        """schedule_freshness_job adds a job to the APScheduler instance."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)
        scheduler._scheduler = MagicMock()

        async def _run():
            await scheduler.schedule_freshness_job(1, "0 */6 * * *", 3)

        asyncio.run(_run())

        scheduler._scheduler.add_job.assert_called_once()
        call_args = scheduler._scheduler.add_job.call_args
        assert call_args.kwargs["id"] == "freshness_group_1"
        assert call_args.kwargs["replace_existing"] is True
        assert 1 in scheduler._freshness_jobs

    def test_schedule_sync_job_no_scheduler(self):
        """schedule_sync_job is a no-op when scheduler hasn't been started."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)

        async def _run():
            await scheduler.schedule_sync_job(1, "*/30 * * * *", 5)

        asyncio.run(_run())
        assert 1 not in scheduler._sync_jobs

    def test_reschedule_sync_job_replaces_existing(self):
        """Scheduling a job for the same group replaces the old job."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)
        scheduler._scheduler = MagicMock()

        async def _run():
            await scheduler.schedule_sync_job(1, "*/30 * * * *", 5)
            await scheduler.schedule_sync_job(1, "0 * * * *", 10)

        asyncio.run(_run())

        # Should be called twice (first add, then replace)
        assert scheduler._scheduler.add_job.call_count == 2
        last_call = scheduler._scheduler.add_job.call_args
        assert last_call.kwargs["args"] == [1, 10]


# ---------------------------------------------------------------------------
# Test remove_sync_job / remove_freshness_job
# ---------------------------------------------------------------------------


class TestRemoveJobs:
    """Tests for removing scheduled jobs."""

    def test_remove_sync_job_removes_from_dict(self):
        """remove_sync_job removes the job id from internal dict and calls
        APScheduler.remove_job."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)
        scheduler._scheduler = MagicMock()
        scheduler._sync_jobs[1] = "sync_group_1"

        scheduler.remove_sync_job(1)

        assert 1 not in scheduler._sync_jobs
        scheduler._scheduler.remove_job.assert_called_once_with("sync_group_1")

    def test_remove_sync_job_nonexistent(self):
        """remove_sync_job on a non-existent group is a no-op."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)
        scheduler._scheduler = MagicMock()

        scheduler.remove_sync_job(999)
        scheduler._scheduler.remove_job.assert_not_called()

    def test_remove_freshness_job_removes_from_dict(self):
        """remove_freshness_job removes the job id from internal dict."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)
        scheduler._scheduler = MagicMock()
        scheduler._freshness_jobs[2] = "freshness_group_2"

        scheduler.remove_freshness_job(2)

        assert 2 not in scheduler._freshness_jobs
        scheduler._scheduler.remove_job.assert_called_once_with("freshness_group_2")


# ---------------------------------------------------------------------------
# Test start / stop lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """Tests for SyncScheduler.start() and stop()."""

    @pytest.mark.asyncio
    async def test_start_schedules_jobs_for_active_groups(self):
        """start() creates an AsyncIOScheduler and calls _schedule_all_jobs."""
        factory, mock_db = _mock_session_factory()

        # Seed get_active_sync_groups with two groups
        groups = [
            _make_group(1),
            _make_group(2, freshness_enabled=False, freshness_cron=None),
        ]

        with (
            patch(
                "app.services.sync_scheduler.SyncGroupService.get_active_sync_groups",
                new_callable=AsyncMock,
                return_value=groups,
            ),
            patch("app.services.sync_scheduler.AsyncIOScheduler") as mock_scheduler_cls,
        ):
            mock_scheduler_instance = MagicMock()
            mock_scheduler_cls.return_value = mock_scheduler_instance

            scheduler = SyncScheduler(factory)
            await scheduler.start()

            mock_scheduler_cls.assert_called_once_with(timezone="UTC")
            mock_scheduler_instance.start.assert_called_once()

            # Both groups get sync jobs, only group 1 gets freshness
            assert 1 in scheduler._sync_jobs
            assert 2 in scheduler._sync_jobs
            assert 1 in scheduler._freshness_jobs
            assert 2 not in scheduler._freshness_jobs

    def test_stop_shuts_down_scheduler(self):
        """stop() calls scheduler.shutdown() and clears the reference."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)
        mock_scheduler = MagicMock()
        scheduler._scheduler = mock_scheduler

        async def _run():
            await scheduler.stop()

        asyncio.run(_run())

        mock_scheduler.shutdown.assert_called_once_with(wait=True)
        assert scheduler._scheduler is None

    def test_stop_no_scheduler_is_safe(self):
        """stop() does not crash when called before start()."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)

        async def _run():
            await scheduler.stop()

        asyncio.run(_run())  # Should not raise


# ---------------------------------------------------------------------------
# Test invalid cron handling
# ---------------------------------------------------------------------------


class TestInvalidCron:
    """Tests for invalid cron expression handling."""

    def test_invalid_cron_schedule_sync_job(self):
        """schedule_sync_job with invalid cron raises ValueError."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)
        scheduler._scheduler = MagicMock()

        async def _run():
            with pytest.raises(ValueError, match="Wrong number of fields"):
                await scheduler.schedule_sync_job(1, "not-a-cron", 5)

        asyncio.run(_run())
        # add_job is never called because validation happens first
        scheduler._scheduler.add_job.assert_not_called()

    def test_invalid_cron_not_added_to_jobs_dict(self):
        """When add_job raises, the job id is NOT added to the internal dict."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)
        scheduler._scheduler = MagicMock()
        scheduler._scheduler.add_job.side_effect = ValueError("Invalid cron")

        async def _run():
            with contextlib.suppress(ValueError):
                await scheduler.schedule_sync_job(1, "bad", 5)

        asyncio.run(_run())
        assert 1 not in scheduler._sync_jobs


# ---------------------------------------------------------------------------
# Test semaphore / concurrency
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Tests for asyncio.Semaphore-based concurrency control."""

    def test_semaphore_created_with_correct_value(self):
        """_get_semaphore creates a semaphore with the group's concurrency."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)

        sem = scheduler._get_semaphore(1, 5)
        assert isinstance(sem, asyncio.Semaphore)
        assert sem._value == 5  # internal counter

    def test_semaphore_reused_for_same_group(self):
        """_get_semaphore returns the same semaphore for the same group."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)

        sem1 = scheduler._get_semaphore(1, 5)
        sem2 = scheduler._get_semaphore(1, 10)  # concurrency ignored after creation
        assert sem1 is sem2

    def test_semaphore_minimum_one(self):
        """Concurrency is clamped to at least 1."""
        factory, _ = _mock_session_factory()
        scheduler = SyncScheduler(factory)

        sem = scheduler._get_semaphore(1, 0)
        assert sem._value == 1

        sem2 = scheduler._get_semaphore(2, -5)
        assert sem2._value == 1


# ---------------------------------------------------------------------------
# Test error handling in job coroutines
# ---------------------------------------------------------------------------


class TestJobErrorHandling:
    """Tests that individual mirror errors don't break the whole group."""

    @pytest.mark.asyncio
    async def test_run_sync_handles_mirror_error_gracefully(self):
        """One failing mirror doesn't prevent other mirrors from syncing."""
        factory, mock_db = _mock_session_factory()

        from app.models.mirror import Mirror

        mirrors = [
            MagicMock(spec=Mirror, id=1),
            MagicMock(spec=Mirror, id=2),
            MagicMock(spec=Mirror, id=3),
        ]

        # First mirror succeeds, second fails, third succeeds
        call_count = 0

        async def _trigger_sync(db, mirror_id, user_id, username):
            nonlocal call_count
            call_count += 1
            if mirror_id == 2:
                raise RuntimeError("Simulated gitlab failure")
            return MagicMock()

        with (
            patch(
                "app.services.sync_scheduler.MirrorService.get_mirrors_by_group",
                new_callable=AsyncMock,
                return_value=mirrors,
            ),
            patch(
                "app.services.sync_scheduler.MirrorService.trigger_sync",
                side_effect=_trigger_sync,
            ),
            patch(
                "app.services.sync_scheduler.SyncScheduler._resolve_user_id",
                new_callable=AsyncMock,
                return_value=1,
            ),
        ):
            scheduler = SyncScheduler(factory)
            await scheduler._run_sync_for_group(1, 3)

            # All three mirrors should have been attempted
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_run_freshness_handles_mirror_error_gracefully(self):
        """One failing freshness check doesn't prevent other mirrors from
        being checked."""
        factory, mock_db = _mock_session_factory()

        from app.models.mirror import Mirror

        mirrors = [
            MagicMock(spec=Mirror, id=1),
            MagicMock(spec=Mirror, id=2),
        ]

        call_count = 0

        async def _check_freshness(db, mirror_id, username):
            nonlocal call_count
            call_count += 1
            if mirror_id == 1:
                raise RuntimeError("Simulated provider failure")
            return MagicMock()

        with (
            patch(
                "app.services.sync_scheduler.MirrorService.get_mirrors_by_group",
                new_callable=AsyncMock,
                return_value=mirrors,
            ),
            patch(
                "app.services.sync_scheduler.MirrorService.check_freshness",
                side_effect=_check_freshness,
            ),
        ):
            scheduler = SyncScheduler(factory)
            await scheduler._run_freshness_for_group(1, 2)

            assert call_count == 2

    @pytest.mark.asyncio
    async def test_run_sync_empty_mirrors_noop(self):
        """When a group has no mirrors, _run_sync_for_group logs and returns."""
        factory, mock_db = _mock_session_factory()

        with (
            patch(
                "app.services.sync_scheduler.MirrorService.get_mirrors_by_group",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "app.services.sync_scheduler.MirrorService.trigger_sync",
                new_callable=AsyncMock,
            ) as mock_trigger,
        ):
            scheduler = SyncScheduler(factory)
            await scheduler._run_sync_for_group(1, 3)

            mock_trigger.assert_not_called()


# ---------------------------------------------------------------------------
# Test _resolve_user_id
# ---------------------------------------------------------------------------


class TestResolveUserID:
    """Tests for _resolve_user_id caching and fallback."""

    @pytest.mark.asyncio
    async def test_resolve_returns_cached_value(self):
        """Second call returns cached user_id without querying DB."""
        factory, mock_db = _mock_session_factory()
        scheduler = SyncScheduler(factory)

        # Pre-cache
        scheduler._system_user_id = 42

        user_id = await scheduler._resolve_user_id(mock_db)
        assert user_id == 42
        # No DB queries should be executed
        mock_db.execute.assert_not_called()
