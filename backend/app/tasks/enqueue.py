"""Enqueue helper for schedulers (APScheduler stays enqueue-only).

Publish errors are caught and logged: enqueue failure must not crash
the API request path (the pass is simply skipped this tick).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)


async def enqueue(task_call: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> None:
    """Publish a task via the broker (task_call.kiq); never raises."""
    try:
        await task_call.kiq(*args, **kwargs)
    except Exception:
        logger.exception("enqueue failed for %s", getattr(task_call, "__name__", task_call))
