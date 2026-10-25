"""
@file test_reaper.py
@description Unit tests for the PEL reaper (ADR-0039 Phase 4, issue #116):
              claimable entries re-added and acked, poison ceiling stops the
              re-add loop, empty PEL is a no-op, cron job enqueues the pass.
@dependencies pytest, unittest.mock
@relatedFiles ../../app/tasks/reaper.py, ../../app/services/scheduler.py
"""

import contextlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import settings
from app.services.scheduler import scheduler_service
from app.tasks.reaper import reap_pending, reap_pending_task


def _msg(task_id: str, task_name: str = "sync_all_task") -> dict[bytes, bytes]:
    return {
        b"data": json.dumps(
            {"task_id": task_id, "task_name": task_name, "args": [], "kwargs": {}}
        ).encode()
    }


def _redis(entries: list[tuple[str, dict[bytes, bytes]]]) -> MagicMock:
    """Fake redis with XAUTOCLAIM always returning *entries* once, then empty."""
    redis = MagicMock()
    redis.xautoclaim = AsyncMock(side_effect=[["0-0", entries, []], ["0-0", [], []]])
    redis.xack = AsyncMock()
    redis.xadd = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.xlen = AsyncMock(return_value=42)
    redis.xpending = AsyncMock(
        return_value={"pending": 1, "oldest": ("1234-1", "worker", 9_000_000, 1)}
    )
    return redis


class TestReapPending:
    async def test_claimable_entries_readded_and_acked(self):
        entries = [("1-1", _msg("t1")), ("2-2", _msg("t2"))]
        redis = _redis(entries)

        claimed = await reap_pending(redis)

        assert claimed == 2
        assert redis.xadd.await_count == 2
        assert redis.xack.await_count == 2

    async def test_readd_then_ack_order(self):
        """Re-add before ack: crash in between costs a duplicate, never a loss."""
        redis = _redis([("1-1", _msg("t1"))])
        order: list[str] = []

        redis.xadd.side_effect = lambda *a, **k: order.append("xadd")
        redis.xack.side_effect = lambda *a, **k: order.append("xack")

        await reap_pending(redis)
        assert order == ["xadd", "xack"]

    async def test_empty_pel_is_noop(self):
        redis = _redis([])
        claimed = await reap_pending(redis)
        assert claimed == 0
        redis.xadd.assert_not_awaited()
        redis.xack.assert_not_awaited()
        redis.xautoclaim.assert_awaited_once()

    async def test_xautoclaim_uses_idle_timeout_and_reaper_consumer(self):
        redis = _redis([])
        await reap_pending(redis)
        call = redis.xautoclaim.await_args
        assert call.args[0] == "taskiq"  # stream from broker config
        assert call.args[1] == "taskiq"  # consumer group from broker config
        assert call.args[2] == "reaper"
        assert call.kwargs["min_idle_time"] == settings.task_idle_timeout_ms

    async def test_poison_ceiling_stops_readding(self, caplog):
        entries = [("1-1", _msg("poisoned"))]
        redis = _redis(entries)
        redis.incr = AsyncMock(return_value=4)  # ceiling is 3

        with (
            patch("app.tasks.reaper._write_poison_events", new_callable=AsyncMock) as wr,
            caplog.at_level("ERROR", logger="app.tasks.reaper"),
        ):
            claimed = await reap_pending(redis)

        assert claimed == 0
        redis.xadd.assert_not_awaited()
        redis.xack.assert_awaited_once()
        wr.assert_awaited_once_with(["sync_all_task:poisoned"])
        assert any("poison entry" in r.message for r in caplog.records)

    async def test_pass_logs_observability_fields(self, caplog):
        redis = _redis([])
        with caplog.at_level("INFO", logger="app.tasks.reaper"):
            await reap_pending(redis)
        line = caplog.records[-1].getMessage()
        assert "stream_len=42" in line
        assert "pel_size=1" in line
        assert "oldest_pending_ms=9000000" in line


class TestReaperTask:
    async def test_task_labels_match_adr(self):
        assert reap_pending_task.labels["max_retries"] == settings.task_max_retries
        assert reap_pending_task.labels["ack_type"] == settings.task_ack_type


class TestReaperCronJob:
    @contextlib.asynccontextmanager
    async def _locked(self):
        yield True

    async def test_reaper_job_enqueues_task(self):
        with (
            patch(
                "app.services.scheduler.job_pass_lock",
                return_value=contextlib.nullcontext(enter_result=True),
            ) as mock_lock,
            patch("app.services.scheduler.reap_pending_task") as mock_task,
            patch("app.services.scheduler.enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            await scheduler_service._run_reaper_job()

        mock_lock.assert_called_once_with("reaper")
        mock_enqueue.assert_awaited_once_with(mock_task)

    async def test_reaper_job_lock_skip_no_enqueue(self):
        with (
            patch(
                "app.services.scheduler.job_pass_lock",
                return_value=contextlib.nullcontext(enter_result=False),
            ),
            patch("app.services.scheduler.enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            await scheduler_service._run_reaper_job()

        mock_enqueue.assert_not_awaited()

    async def test_start_registers_reaper_cron(self):
        scheduler_service.scheduler = MagicMock()
        try:
            await scheduler_service.start()
        finally:
            await scheduler_service.stop()

        job_ids = [c.kwargs.get("id") for c in scheduler_service.scheduler.add_job.call_args_list]
        assert "reaper" in job_ids
