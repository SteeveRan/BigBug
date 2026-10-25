"""
@file test_sync_run_tracking.py
@description Unit tests for the unified sync-run tracking wrapper (issue #112):
             status transitions incl. failed_permanent after exhausting
             retries, retry row-reuse (attempts increment), heartbeat pulse,
             stuck window, and best-effort semantics (tracking DB failure must
             not break the task body).
@dependencies pytest, unittest.mock
@relatedFiles ../../app/tasks/run_tracking.py
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import settings
from app.tasks import run_tracking
from app.tasks.run_tracking import _heartbeat_loop, is_stuck, run_tracked


def _db_factory(capture: dict):
    """Mock AsyncSessionLocal: each session's execute() returns no prior row
    (fresh run); added objects and executed statements land in capture."""
    run_holder: dict = {}
    statements: list = []
    sessions: list = []

    def _mk_db():
        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        db.execute.side_effect = lambda stmt, *a, **k: (
            statements.append(stmt),
            db.execute.return_value,
        )[1]
        sessions.append(db)
        return db

    def _add(obj):
        run_holder["run"] = obj

    def _factory(*args, **kwargs):
        db = _mk_db()
        db.add = MagicMock(side_effect=_add)  # add() is sync on a real session
        return db.__aenter__.return_value if False else _ctx(db)

    def _ctx(db):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=db)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    factory = MagicMock(side_effect=_factory)
    capture.update(statements=statements, run_holder=run_holder, sessions=sessions)
    return factory


class TestTrackSyncRun:
    async def test_success_marks_succeeded(self):
        capture: dict = {}

        async def _body():
            return "ok"

        with patch.object(run_tracking, "AsyncSessionLocal", _db_factory(capture)):
            result = await run_tracked("t1", _body)

        assert result == "ok"
        run = capture["run_holder"]["run"]
        assert run.status == "running"  # success is stamped via a separate UPDATE
        assert run.attempts == 1
        assert run.started_at is not None
        # exit UPDATE carries the succeeded status
        from sqlalchemy.dialects import postgresql

        exit_stmt = capture["statements"][-1]
        compiled = str(
            exit_stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )
        assert "'succeeded'" in compiled

    async def test_first_failure_is_failed(self):
        capture: dict = {}

        async def _body():
            raise RuntimeError("boom")

        with (
            patch.object(run_tracking, "AsyncSessionLocal", _db_factory(capture)),
            contextlib.suppress(RuntimeError),
        ):
            await run_tracked("t1", _body)

        # Exit path (failure) must run its own UPDATE + commit on a new session
        from sqlalchemy import Update

        assert len(capture["statements"]) == 2  # enter SELECT + exit UPDATE
        exit_stmt = capture["statements"][-1]
        assert isinstance(exit_stmt, Update)
        assert len(capture["sessions"]) >= 2
        assert capture["sessions"][-1].commit.await_count >= 1

    async def test_failed_permanent_after_exhausting_retries(self):
        """The failure update flips to failed_permanent when attempts reach
        max_attempts — taskiq's retry middleware re-runs the body and the
        wrapper reuses the failed row, incrementing attempts."""
        capture: dict = {}
        run_obj = MagicMock()
        run_obj.attempts = settings.task_max_retries  # 3rd attempt
        run_obj.max_attempts = settings.task_max_retries

        async def _body():
            raise RuntimeError("boom")

        factory_db = AsyncMock()
        factory_db.execute.return_value = MagicMock(
            scalar_one_or_none=MagicMock(return_value=run_obj)
        )
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=factory_db)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)
        capture["db"] = factory_db

        with (
            patch.object(run_tracking, "AsyncSessionLocal", factory),
            contextlib.suppress(RuntimeError),
        ):
            await run_tracked("t1", _body)

        # Failure update must carry failed_permanent (compile the UPDATE with
        # literal params to inspect the bound values).
        from sqlalchemy.dialects import postgresql

        update_stmt = factory_db.execute.await_args_list[-1].args[0]
        compiled = str(
            update_stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        assert "failed_permanent" in compiled

    async def test_tracking_db_failure_does_not_break_body(self):
        """Best-effort: if sync_runs is unavailable the body still runs."""
        broken_factory = MagicMock()
        broken_factory.return_value.__aenter__ = AsyncMock(side_effect=ConnectionError("no db"))

        calls: list[str] = []

        async def _body():
            calls.append("ran")
            return 42

        with patch.object(run_tracking, "AsyncSessionLocal", broken_factory):
            result = await run_tracked("t1", _body)

        assert calls == ["ran"]
        assert result == 42

    async def test_reuses_failed_row_increments_attempts(self):
        run_obj = MagicMock()
        run_obj.attempts = 1
        run_obj.max_attempts = settings.task_max_retries

        db = AsyncMock()
        db.execute.return_value = MagicMock(scalar_one_or_none=MagicMock(return_value=run_obj))
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=db)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)

        async def _body():
            return None

        with patch.object(run_tracking, "AsyncSessionLocal", factory):
            await run_tracked("t1", _body)

        assert run_obj.attempts == 2
        assert run_obj.status == "running"


class TestHeartbeatAndStuck:
    async def test_heartbeat_loop_pulses(self):
        """The ticker writes heartbeat_at at its interval."""
        db = AsyncMock()
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=db)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch.object(run_tracking.settings, "sync_heartbeat_interval_seconds", 0.01),
            patch.object(run_tracking, "AsyncSessionLocal", factory),
        ):
            task = asyncio.create_task(_heartbeat_loop(7))
            await asyncio.sleep(0.05)
            task.cancel()
            with __import__("contextlib").suppress(asyncio.CancelledError):
                await task

        assert db.execute.await_count >= 2
        assert db.commit.await_count >= 2

    def test_is_stuck_window(self):
        fresh = datetime.now(UTC)
        old = fresh - timedelta(minutes=settings.sync_stuck_after_minutes + 1)
        assert not is_stuck("running", fresh)
        assert is_stuck("running", old)
        assert not is_stuck("failed", old)
        assert not is_stuck("running", None)
        assert not is_stuck("succeeded", old)
