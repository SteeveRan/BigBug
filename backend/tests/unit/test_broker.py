"""Unit tests for the taskiq broker module, enqueue helper, and job-pass lock."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from taskiq.result_backends.dummy import DummyResultBackend

from app.config import settings
from app.tasks.broker import broker
from app.tasks.enqueue import enqueue
from app.tasks.pass_lock import job_pass_lock


def test_broker_defaults_match_adr():
    assert broker.queue_name == "taskiq"
    # at-least-once: idle timeout 30 min, explicit unacknowledged lock timeout
    assert broker.idle_timeout == settings.task_idle_timeout_ms
    assert broker.idle_timeout == 1_800_000
    assert broker.unacknowledged_lock_timeout == 60
    # no result backend — DummyResultBackend is the default
    assert isinstance(broker.result_backend, DummyResultBackend)


def test_config_task_settings_defaults():
    assert settings.task_ack_type == "when_executed"
    assert settings.task_max_retries == 3


async def test_enqueue_success():
    task_call = MagicMock()
    task_call.__name__ = "noop"
    task_call.kiq = AsyncMock()
    await enqueue(task_call, 1, x="a")
    task_call.kiq.assert_awaited_once_with(1, x="a")


async def test_enqueue_swallows_publish_error(caplog):
    task_call = MagicMock()
    task_call.__name__ = "noop"
    task_call.kiq = AsyncMock(side_effect=ConnectionError("redis down"))
    with caplog.at_level("ERROR"):
        await enqueue(task_call)  # must not raise
    assert any("enqueue failed" in r.message for r in caplog.records)


async def test_lock_acquire_skip_release():
    redis = MagicMock()
    redis.set = AsyncMock(side_effect=[True, False])
    redis.delete = AsyncMock()

    # first pass acquires
    async with job_pass_lock("sync_all", client=redis) as acquired:
        assert acquired is True
    redis.delete.assert_awaited_once()

    # second concurrent pass is skipped and does not release
    async with job_pass_lock("sync_all", client=redis) as acquired:
        assert acquired is False
    assert redis.delete.await_count == 1


async def test_lock_released_on_exception():
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    with pytest.raises(ValueError, match="task failed"):
        async with job_pass_lock("boom", client=redis):
            raise ValueError("task failed")
    redis.delete.assert_awaited_once()


async def test_lock_uses_settings_url_by_default():
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock()
    calls: list[str] = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.tasks.pass_lock._get_client", lambda url: calls.append(url) or redis)
        async with job_pass_lock("x") as acquired:
            assert acquired is True
    assert calls == [settings.redis_url]
