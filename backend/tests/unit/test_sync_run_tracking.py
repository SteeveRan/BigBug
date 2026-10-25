"""
@file test_sync_run_tracking.py
@description Tests for the unified sync-run tracking wrapper (issue #112),
             executed against the real in-memory SQLite schema:
             queued-row atomic claim (incl. concurrent-claim race),
             status transitions incl. failed_permanent after exhausting
             retries, failed-row reuse (attempts increment), heartbeat pulse,
             stuck window (running + stale heartbeat, phantom queued),
             and best-effort semantics (tracking DB failure must not break
             the task body).
@dependencies pytest, sqlalchemy
@relatedFiles ../../app/tasks/run_tracking.py, ../../app/tasks/enqueue.py
"""

import asyncio
import contextlib
import unittest.mock as mock
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.models.sync_run import SyncRun
from app.tasks import run_tracking
from app.tasks.enqueue import enqueue
from app.tasks.run_tracking import _heartbeat_loop, is_stuck, run_tracked


@pytest.fixture
def tracking_db(db_transaction):
    """Patch run_tracking/enqueue to use the per-test transaction-scoped DB."""
    factory = async_sessionmaker(
        bind=db_transaction,
        join_transaction_mode="create_savepoint",
        class_=AsyncSession,
        expire_on_commit=False,
    )
    with (
        mock.patch.object(run_tracking, "AsyncSessionLocal", factory),
        mock.patch("app.tasks.enqueue.AsyncSessionLocal", factory),
    ):
        yield factory


async def _get_run(db: AsyncSession) -> SyncRun:
    return (await db.execute(select(SyncRun).order_by(SyncRun.id.desc()).limit(1))).scalar_one()


class TestTrackSyncRun:
    async def test_success_marks_succeeded(self, tracking_db, db_session):
        async def _body():
            return "ok"

        result = await run_tracked("t1", _body, payload={"args": [], "kwargs": {}})

        assert result == "ok"
        run = await _get_run(db_session)
        assert run.status == "succeeded"
        assert run.attempts == 1
        assert run.started_at is not None
        assert run.finished_at is not None
        assert run.heartbeat_at is not None

    async def test_first_failure_is_failed(self, tracking_db, db_session):
        async def _body():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await run_tracked("t1", _body)

        run = await _get_run(db_session)
        assert run.status == "failed"
        assert "boom" in run.error
        assert run.finished_at is not None

    async def test_failed_permanent_after_exhausting_retries(self, tracking_db, db_session):
        """Retry semantics: after a failed run, a re-execution (taskiq retry
        middleware) reuses the failed row; at attempts >= max_attempts the
        status flips to failed_permanent."""

        async def _body():
            raise RuntimeError("boom")

        for _ in range(settings.task_max_retries):
            with contextlib.suppress(RuntimeError):
                await run_tracked("t1", _body)

        runs = (
            (await db_session.execute(select(SyncRun).order_by(SyncRun.id.asc()))).scalars().all()
        )
        assert len(runs) == 1  # one logical run, attempts incremented
        assert runs[0].status == "failed_permanent"
        assert runs[0].attempts == settings.task_max_retries

    async def test_claims_queued_row_written_by_enqueue(self, tracking_db, db_session):
        """enqueue() writes a queued row before publish; the wrapper claims it
        atomically instead of creating a duplicate row."""
        task_call = mock.MagicMock()
        task_call.__name__ = "t_claim"
        task_call.kiq = mock.AsyncMock()
        await enqueue(task_call, 1, x="a", entity_type="sync_group", entity_id=9)

        async def _body():
            return None

        await run_tracked("t_claim", _body, entity_type="sync_group", entity_id=9)

        runs = (await db_session.execute(select(SyncRun))).scalars().all()
        assert len(runs) == 1
        run = runs[0]
        assert run.status == "succeeded"
        assert run.attempts == 1  # 0 (queued) + 1 on start
        assert run.entity_type == "sync_group"
        assert run.entity_id == 9
        assert run.payload == {"args": [1], "kwargs": {"x": "a"}}

    async def test_no_queued_row_creates_fresh_run(self, tracking_db, db_session):
        async def _body():
            return None

        await run_tracked("t_fresh", _body, entity_type="mirror", entity_id=3)

        run = await _get_run(db_session)
        assert run.status == "succeeded"
        assert run.attempts == 1
        assert run.payload is None

    async def test_tracking_db_failure_does_not_break_body(self, db_transaction):
        """Best-effort: if sync_runs is unavailable the body still runs."""
        broken = mock.MagicMock()
        broken.return_value.__aenter__ = mock.AsyncMock(side_effect=ConnectionError("no db"))
        calls: list[str] = []

        async def _body():
            calls.append("ran")
            return 42

        with mock.patch.object(run_tracking, "AsyncSessionLocal", broken):
            result = await run_tracked("t1", _body)

        assert calls == ["ran"]
        assert result == 42


class TestHeartbeatAndStuck:
    async def test_heartbeat_loop_pulses(self, tracking_db):
        """The ticker never raises on a missing run id."""
        with mock.patch.object(run_tracking.settings, "sync_heartbeat_interval_seconds", 0.01):
            task = asyncio.create_task(_heartbeat_loop(7))
            await asyncio.sleep(0.05)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def test_heartbeat_updates_row(self, tracking_db):
        async with tracking_db() as db:
            run = SyncRun(
                task_name="t_hb",
                status="running",
                attempts=1,
                max_attempts=3,
                heartbeat_at=datetime.now(UTC) - timedelta(hours=1),
            )
            db.add(run)
            await db.commit()
            run_id = run.id

        with mock.patch.object(run_tracking.settings, "sync_heartbeat_interval_seconds", 0.01):
            task = asyncio.create_task(_heartbeat_loop(run_id))
            await asyncio.sleep(0.05)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        async with tracking_db() as db:
            row = (await db.execute(select(SyncRun).where(SyncRun.id == run_id))).scalar_one()
            assert (datetime.now(UTC) - row.heartbeat_at.replace(tzinfo=UTC)).total_seconds() < 10

    def test_is_stuck_window(self):
        fresh = datetime.now(UTC)
        old = fresh - timedelta(minutes=settings.sync_stuck_after_minutes + 1)
        assert not is_stuck("running", fresh)
        assert is_stuck("running", old)
        assert not is_stuck("failed", old)
        assert not is_stuck("running", None)
        assert not is_stuck("succeeded", old)

    def test_is_stuck_phantom_queued(self):
        old_created = datetime.now(UTC) - timedelta(minutes=settings.sync_stuck_after_minutes + 1)
        fresh_created = datetime.now(UTC)
        assert is_stuck("queued", None, old_created)
        assert not is_stuck("queued", None, fresh_created)
        assert not is_stuck("queued", None, None)


class TestEnqueueQueuedRow:
    async def test_enqueue_writes_queued_row_before_publish(self, tracking_db):
        task_call = mock.MagicMock()
        task_call.__name__ = "t_pub"
        task_call.kiq = mock.AsyncMock()

        await enqueue(task_call, 1, 2, key="v", entity_type="sync_group", entity_id=5)

        task_call.kiq.assert_awaited_once_with(1, 2, key="v")
        async with tracking_db() as db:
            run = await _get_run(db)
            assert run.status == "queued"
            assert run.task_name == "t_pub"
            assert run.entity_type == "sync_group"
            assert run.entity_id == 5
            assert run.payload == {"args": [1, 2], "kwargs": {"key": "v"}}

    async def test_enqueue_broker_failure_keeps_queued_row(self, tracking_db):
        """DB-as-DLQ: publish fails → the queued row remains, task not lost."""
        task_call = mock.MagicMock()
        task_call.__name__ = "t_lost"
        task_call.kiq = mock.AsyncMock(side_effect=ConnectionError("redis down"))

        await enqueue(task_call)  # must not raise

        async with tracking_db() as db:
            runs = (await db.execute(select(SyncRun))).scalars().all()
            assert len(runs) == 1
            assert runs[0].status == "queued"
            assert runs[0].task_name == "t_lost"

    async def test_enqueue_db_failure_still_publishes(self, db_transaction):
        """Tracking write failed → kiq must still happen (best-effort)."""
        import unittest.mock as mock

        task_call = mock.MagicMock()
        task_call.__name__ = "t_kiq"
        task_call.kiq = mock.AsyncMock()

        broken = mock.MagicMock()
        broken.return_value.__aenter__ = mock.AsyncMock(side_effect=ConnectionError("no db"))
        with mock.patch("app.tasks.enqueue.AsyncSessionLocal", broken):
            await enqueue(task_call, 7)

        task_call.kiq.assert_awaited_once_with(7)


class TestConcurrentClaim:
    async def test_claim_guard_single_winner(self, tracking_db, db_session):
        """Atomic claim: the guarded UPDATE (WHERE status='queued') can win
        only once — a second claimant gets rowcount 0 and falls back to a
        fresh row. Simulated sequentially (true parallel sessions would
        interleave savepoints on the shared test connection)."""
        task_call = mock.MagicMock()
        task_call.__name__ = "t_race"
        task_call.kiq = mock.AsyncMock()
        await enqueue(task_call)

        async with tracking_db() as db1:
            run1 = await run_tracking._claim_or_create_run(db1, "t_race", None, None, None)
            await db1.commit()
        async with tracking_db() as db2:
            run2 = await run_tracking._claim_or_create_run(db2, "t_race", None, None, None)
            await db2.commit()

        runs = (
            (await db_session.execute(select(SyncRun).order_by(SyncRun.id.asc()))).scalars().all()
        )
        assert len(runs) == 2
        assert [r.id for r in runs] == [run1.id, run2.id]
        assert run1.attempts == 1  # claimed the queued row (0 + 1)
        assert run1.status == "running"
        assert run2.attempts == 1  # fresh fallback row
        assert run2.id != run1.id
        assert run1.id != run2.id

    async def test_no_duplicate_rows_after_repeated_runs(self, tracking_db):
        task_call = mock.MagicMock()
        task_call.__name__ = "t_seq"
        task_call.kiq = mock.AsyncMock()

        async def _body():
            return None

        for _ in range(3):
            await enqueue(task_call)
            await run_tracked("t_seq", _body)

        async with tracking_db() as db:
            count = (await db.execute(select(func.count()).select_from(SyncRun))).scalar_one()
            assert count == 3
            statuses = [r.status for r in (await db.execute(select(SyncRun))).scalars()]
            assert statuses == ["succeeded", "succeeded", "succeeded"]
