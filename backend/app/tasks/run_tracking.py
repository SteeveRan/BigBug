"""Unified sync-run tracking (issue #112, ADR-0039 Phase 4).

Wraps task bodies — never business services — with a ``sync_runs`` row plus a
heartbeat pulse. Best-effort by design: tracking errors are logged and never
fail the tracked task.

Row lifecycle (DB-as-DLQ): ``enqueue()`` writes a ``queued`` row before
publishing; on start this wrapper atomically claims the newest queued row for
the task name (guarded UPDATE, rowcount check — no double adoption). If there
is no queued row to claim (broker-publish failed after the row write failed,
or a taskiq middleware retry, which bypasses enqueue), the newest "failed" row
of the same (task_name, entity_type, entity_id) key is reused (one row per
logical run, attempts incremented); otherwise a fresh row is created.
A manual retry via the admin API enqueues a fresh run that starts at
attempts=1. "Stuck" is computed: running with stale heartbeat, or queued
longer than the stuck window (phantom row after a broker outage).
"""

import asyncio
import contextlib
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


async def _claim_or_create_run(
    db,
    task_name: str,
    entity_type: str | None,
    entity_id: int | None,
    payload: dict[str, Any] | None,
) -> SyncRun:
    """Atomic claim of the newest queued row, with fallbacks.

    1. Claim: guarded UPDATE (WHERE status='queued') — two concurrent workers
       of the same task cannot both win; the loser's rowcount is 0.
    2. Fallback A (taskiq middleware retry / queued-row write failed):
       reuse the newest "failed" row of the same key → attempts+1.
    3. Fallback B: fresh "running" row.
    """
    now = _now()

    queued_id_result = await db.execute(
        select(SyncRun.id)
        .where(SyncRun.task_name == task_name, SyncRun.status == "queued")
        .order_by(SyncRun.id.desc())
        .limit(1)
    )
    queued_id = queued_id_result.scalar_one_or_none()
    if queued_id is not None:
        claim = await db.execute(
            update(SyncRun)
            .where(SyncRun.id == queued_id, SyncRun.status == "queued")
            .values(
                status="running",
                attempts=SyncRun.attempts + 1,
                entity_type=entity_type,
                entity_id=entity_id,
                started_at=now,
                heartbeat_at=now,
                error=None,
                finished_at=None,
            )
        )
        if claim.rowcount == 1:
            result = await db.execute(select(SyncRun).where(SyncRun.id == queued_id))
            return result.scalar_one()

    # Broker-middleware retry (bypasses enqueue): reuse the failed row.
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
    run.started_at = now
    run.heartbeat_at = now
    run.error = None
    run.finished_at = None
    return run


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

    On entry: atomically claim the newest "queued" row for the task name
    (written by enqueue before publish), else reuse the newest "failed" row
    for the same key (retry → attempts+1), else create a fresh "running" row.
    On exit: succeeded, or failed / failed_permanent when attempts reach
    max_attempts. The body exception is always re-raised so the broker retry
    middleware works.
    """
    ticker: asyncio.Task | None = None
    try:
        async with AsyncSessionLocal() as db:
            run = await _claim_or_create_run(db, task_name, entity_type, entity_id, payload)
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
            # Await the cancellation: an un-awaited cancelled task may finish
            # its DB session during a LATER test/transaction on this process.
            with contextlib.suppress(asyncio.CancelledError):
                await ticker


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


def is_stuck(
    status: str,
    heartbeat_at: datetime | None,
    created_at: datetime | None = None,
) -> bool:
    """Stuck = running with a stale heartbeat, or queued past the window
    (phantom row: the broker publish failed — the task never started)."""
    if status == "queued":
        if created_at is None:
            return False
        age = _now() - _aware(created_at)
        return age.total_seconds() >= settings.sync_stuck_after_minutes * 60
    if status != "running" or heartbeat_at is None:
        return False
    stale = _now() - _aware(heartbeat_at)
    return stale.total_seconds() >= settings.sync_stuck_after_minutes * 60


def _aware(dt: datetime) -> datetime:
    # SQLite (tests) returns naive UTC datetimes.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _resolve_task(task_name: str) -> Any:
    """Find a task function by name across the task modules (retry/requeue)."""
    from app.tasks import metadata_tasks, outbox_tasks, reconcile_tasks, sync_tasks

    for mod in (sync_tasks, metadata_tasks, reconcile_tasks, outbox_tasks):
        task = getattr(mod, task_name, None)
        if task is not None:
            return task
    return None
