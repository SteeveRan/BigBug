"""Unified sync-run tracking (issue #112, ADR-0039 Phase 4).

Wraps task bodies — never business services — with a ``sync_runs`` row plus a
heartbeat pulse. Best-effort by design: tracking errors are logged and never
fail the tracked task. Correlation for retries: the newest row for the same
(task_name, entity_type, entity_id) key with status="failed" is reused (one
row per logical run, attempts incremented); a manual retry via the admin API
enqueues a fresh run that finds no row to reuse and starts with attempts=1.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.sync_run import SyncRun

logger = logging.getLogger(__name__)

_ERROR_MAX_LEN = 2000


def _now() -> datetime:
    return datetime.now(UTC)


async def _heartbeat_loop(run_id: int) -> None:
    """Pulse heartbeat_at while the run is alive. Never raises."""
    while True:
        await asyncio.sleep(settings.sync_heartbeat_interval_seconds)
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(SyncRun)
                    .where(SyncRun.id == run_id, SyncRun.status == "running")
                    .values(heartbeat_at=_now())
                )
                await db.commit()
        except Exception:
            logger.exception("Heartbeat pulse failed for sync_run %d", run_id)


@asynccontextmanager
async def track_sync_run(
    task_name: str,
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    payload: dict[str, Any] | None = None,
):
    """Track one task execution as a sync_runs row.

    Usage inside a task body::

        async with track_sync_run("my_task", entity_id=1) as run:
            await do_work()

    On entry: reuse the newest "failed" row for the same key (retry →
    attempts+1) or create a fresh "running" row. On exit: succeeded, or
    failed / failed_permanent when attempts reach max_attempts. The body
    exception is always re-raised so the broker retry middleware works.
    """
    ticker: asyncio.Task | None = None
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SyncRun)
                .where(
                    SyncRun.task_name == task_name,
                    SyncRun.entity_type == entity_type,
                    SyncRun.entity_id == entity_id,
                    SyncRun.status == "failed",
                )
                .order_by(SyncRun.id.desc())
                .limit(1)
            )
            run = result.scalar_one_or_none()
            if run is not None:
                run.attempts += 1
            else:
                run = SyncRun(
                    task_name=task_name,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    payload=payload,
                    attempts=1,
                    max_attempts=settings.task_max_retries,
                )
                db.add(run)
            run.status = "running"
            run.started_at = _now()
            run.heartbeat_at = run.started_at
            run.error = None
            run.finished_at = None
            await db.commit()
            run_id = run.id
            attempts, max_attempts = run.attempts, run.max_attempts
    except Exception:
        logger.exception("sync_runs tracking unavailable for %s; running untracked", task_name)
        # Run untracked: tracking must never break the task.
        yield None
        return

    ticker = asyncio.create_task(_heartbeat_loop(run_id))
    try:
        yield run
    except Exception as exc:
        final = "failed_permanent" if attempts >= max_attempts else "failed"
        error = f"{type(exc).__name__}: {exc}"[:_ERROR_MAX_LEN]
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(SyncRun)
                    .where(SyncRun.id == run_id, SyncRun.status == "running")
                    .values(status=final, error=error, finished_at=_now())
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to record failure for sync_run %d", run_id)
        raise
    else:
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(SyncRun)
                    .where(SyncRun.id == run_id, SyncRun.status == "running")
                    .values(status="succeeded", finished_at=_now())
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to record success for sync_run %d", run_id)
    finally:
        if ticker is not None:
            ticker.cancel()


async def run_tracked(
    task_name: str,
    body: Callable[[], Awaitable[Any]],
    *,
    entity_type: str | None = None,
    entity_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    """Run *body* under track_sync_run; returns the body result."""
    async with track_sync_run(
        task_name, entity_type=entity_type, entity_id=entity_id, payload=payload
    ):
        return await body()


def is_stuck(status: str, heartbeat_at: datetime | None) -> bool:
    """Stuck = running with a heartbeat older than the configured window."""
    if status != "running" or heartbeat_at is None:
        return False
    hb = heartbeat_at
    if hb.tzinfo is None:  # SQLite (tests) returns naive UTC datetimes
        hb = hb.replace(tzinfo=UTC)
    stale = _now() - hb
    return stale.total_seconds() >= settings.sync_stuck_after_minutes * 60


def _resolve_task(task_name: str) -> Any:
    """Find a task function by name across the task modules (retry/requeue)."""
    from app.tasks import metadata_tasks, outbox_tasks, reconcile_tasks, sync_tasks

    for mod in (sync_tasks, metadata_tasks, reconcile_tasks, outbox_tasks):
        task = getattr(mod, task_name, None)
        if task is not None:
            return task
    return None
