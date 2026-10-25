"""Enqueue helper for schedulers (APScheduler stays enqueue-only).

DB-as-DLQ (issue #112): every enqueue first writes a ``queued`` sync_runs row,
*then* publishes to the broker. If the broker is down, the row stays queued —
the task is not silently lost and the admin API can requeue it. Both steps are
best-effort: enqueue failure must not crash the caller (the pass is skipped or
retried later).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.sync_run import SyncRun

logger = logging.getLogger(__name__)


async def enqueue(
    task_call: Callable[..., Awaitable[Any]],
    *args: Any,
    entity_type: str | None = None,
    entity_id: int | None = None,
    **kwargs: Any,
) -> None:
    """Publish a task via the broker (task_call.kiq); never raises.

    ``entity_type``/``entity_id`` are tracking metadata consumed here (not
    forwarded to the task); everything else goes to kiq. The queued row is
    adopted atomically by the task wrapper (app.tasks.run_tracking).
    """
    name = getattr(task_call, "__name__", task_call)
    try:
        async with AsyncSessionLocal() as db:
            db.add(
                SyncRun(
                    task_name=name,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    status="queued",
                    attempts=0,
                    max_attempts=settings.task_max_retries,
                    payload={"args": list(args), "kwargs": kwargs},
                )
            )
            await db.commit()
    except Exception:
        logger.exception("sync_runs queued-row write failed for %s", name)
    try:
        await task_call.kiq(*args, **kwargs)
    except Exception:
        logger.exception("enqueue failed for %s", name)
