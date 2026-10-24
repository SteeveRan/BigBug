"""Unit tests for taskiq task bodies (ADR-0039): task bodies delegate to the
existing services; labels carry retry/ack config; group passes use a per-worker
semaphore and never let one mirror's failure kill the pass."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import settings
from app.tasks.metadata_tasks import fetch_metadata_task, sync_releases_task
from app.tasks.sync_tasks import (
    build_all_task,
    cleanup_task,
    freshness_group_task,
    sync_all_task,
    sync_group_task,
)


async def test_task_labels_match_adr():
    for task in (
        sync_all_task,
        build_all_task,
        cleanup_task,
        sync_group_task,
        freshness_group_task,
        fetch_metadata_task,
        sync_releases_task,
    ):
        assert task.labels["max_retries"] == settings.task_max_retries == 3
        assert task.labels["ack_type"] == settings.task_ack_type == "when_executed"


async def test_sync_group_task_delegates_to_mirror_service():
    """sync_group_task resolves user + triggers sync per mirror with its own session."""
    mirror = MagicMock(id=7)
    db = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = db

    with (
        patch("app.tasks.sync_tasks.AsyncSessionLocal", factory),
        patch(
            "app.tasks.sync_tasks.MirrorService.get_mirrors_by_group",
            new_callable=AsyncMock,
            return_value=[mirror],
        ),
        patch(
            "app.tasks.sync_tasks.MirrorService.trigger_sync",
            new_callable=AsyncMock,
        ) as mock_trigger,
        patch("app.tasks.sync_tasks._resolve_user_id", new_callable=AsyncMock, return_value=42),
    ):
        await sync_group_task(1, 3)

    mock_trigger.assert_awaited_once()
    assert mock_trigger.await_args.kwargs["mirror_id"] == 7
    assert mock_trigger.await_args.kwargs["user_id"] == 42
    assert mock_trigger.await_args.kwargs["username"] == "scheduler"
    assert mock_trigger.await_args.kwargs["db"] is db


async def test_sync_group_task_mirror_error_does_not_kill_pass():
    """One failing mirror is logged; the pass still completes."""
    mirrors = [MagicMock(id=1), MagicMock(id=2)]
    db = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = db

    calls: list[int] = []

    async def _trigger(db, mirror_id, user_id, username):
        calls.append(mirror_id)
        if mirror_id == 1:
            raise RuntimeError("boom")

    with (
        patch("app.tasks.sync_tasks.AsyncSessionLocal", factory),
        patch(
            "app.tasks.sync_tasks.MirrorService.get_mirrors_by_group",
            new_callable=AsyncMock,
            return_value=mirrors,
        ),
        patch("app.tasks.sync_tasks.MirrorService.trigger_sync", side_effect=_trigger),
        patch("app.tasks.sync_tasks._resolve_user_id", new_callable=AsyncMock, return_value=1),
    ):
        await sync_group_task(1, 5)  # must not raise

    assert calls == [1, 2]


async def test_freshness_group_task_delegates_to_check_freshness():
    mirror = MagicMock(id=9)
    db = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = db

    with (
        patch("app.tasks.sync_tasks.AsyncSessionLocal", factory),
        patch(
            "app.tasks.sync_tasks.MirrorService.get_mirrors_by_group",
            new_callable=AsyncMock,
            return_value=[mirror],
        ),
        patch(
            "app.tasks.sync_tasks.MirrorService.check_freshness",
            new_callable=AsyncMock,
        ) as mock_check,
    ):
        await freshness_group_task(1, 3)

    mock_check.assert_awaited_once()
    assert mock_check.await_args.kwargs["mirror_id"] == 9
    assert mock_check.await_args.kwargs["username"] == "scheduler"


async def test_group_pass_semaphore_limits_concurrency():
    """No more than *concurrency* mirror ops run in parallel within a pass."""
    mirrors = [MagicMock(id=i) for i in range(10)]
    db = AsyncMock()
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = db

    running = 0
    peak = 0

    async def _check(db, mirror_id, username):
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0)
        running -= 1

    with (
        patch("app.tasks.sync_tasks.AsyncSessionLocal", factory),
        patch(
            "app.tasks.sync_tasks.MirrorService.get_mirrors_by_group",
            new_callable=AsyncMock,
            return_value=mirrors,
        ),
        patch("app.tasks.sync_tasks.MirrorService.check_freshness", side_effect=_check),
    ):
        await freshness_group_task(1, 2)

    assert peak <= 2


async def test_sync_all_task_delegates_to_docker_service():
    """sync_all_task runs docker sync for due schedules and stamps last_run_at."""
    from datetime import timedelta

    from app.models.sync_schedule import SyncSchedule

    schedule = MagicMock(spec=SyncSchedule)
    schedule.is_enabled = True
    schedule.use_default_schedule = False
    schedule.cron_expression = "*/30 * * * *"
    schedule.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
    schedule.sync_type = "docker_image"
    schedule.docker_image_source_id = 5

    source = MagicMock()
    source.id = 5
    source.target_registry_url = "harbor.local"
    tag = MagicMock(image_name="img", tag="1.0")

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[schedule])))
            ),
            MagicMock(scalar_one_or_none=MagicMock(return_value=source)),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[tag])))),
        ]
    )
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = db

    with (
        patch("app.tasks.sync_tasks.AsyncSessionLocal", factory),
        patch("app.services.docker.docker_service.sync_image", new_callable=AsyncMock) as mock_sync,
    ):
        await sync_all_task()

    mock_sync.assert_awaited_once()
    assert schedule.last_run_at is not None


async def test_build_all_task_delegates_to_build_service():
    from app.models.build_schedule import BuildSchedule

    schedule = MagicMock(spec=BuildSchedule)
    schedule.next_run_at = None
    schedule.image_type = "gold"
    schedule.gold_image_id = 3
    image = MagicMock()

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[schedule])))
            ),
            MagicMock(scalar_one_or_none=MagicMock(return_value=image)),
        ]
    )
    factory = MagicMock()
    factory.return_value.__aenter__.return_value = db

    with (
        patch("app.tasks.sync_tasks.AsyncSessionLocal", factory),
        patch(
            "app.services.build.build_service.trigger_gold_build", new_callable=AsyncMock
        ) as mock_build,
    ):
        await build_all_task()

    mock_build.assert_awaited_once()
    assert mock_build.await_args.args[0] is image
    assert schedule.last_run_at is not None

    async def test_cleanup_task_delegates_to_cleanup_job():
        with patch(
            "app.services.cleanup.CleanupService.run_cleanup", new_callable=AsyncMock
        ) as mock_cleanup:
            await cleanup_task()  # creates its own session
        mock_cleanup.assert_awaited_once()
