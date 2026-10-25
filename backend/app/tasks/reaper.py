"""XAUTOCLAIM reaper for stuck PEL entries (ADR-0039 Phase 4, issue #116).

The belt to the broker's braces (#107 config): PEL entries can sit unclaimed
when a worker died without ack and the broker's own autoclaim path missed
them (taskiq-redis #131 territory). A scheduled pass (enqueue-only, job-pass
lock) inspects the broker's stream consumer group via XPENDING/XAUTOCLAIM;
entries pending longer than ``task_idle_timeout_ms`` are force-claimed,
re-added to the stream for fresh processing, and the old entry acked.

Poison ceiling: a per-task reclaim counter (Redis key with TTL) stops the
re-add loop — entries exceeding the ceiling are logged (ERROR) + written as
an outbox event (visible to the console story) instead of looping forever.
"""

import json
import logging

from redis.asyncio import Redis

from app.config import settings
from app.database import AsyncSessionLocal
from app.tasks.broker import broker
from app.tasks.pass_lock import _get_client
from app.tasks.run_tracking import run_tracked

logger = logging.getLogger(__name__)

_TASK_LABELS = {
    "max_retries": settings.task_max_retries,
    "ack_type": settings.task_ack_type,
}

# Broker topology (single queue, default group — mirror broker.py config).
STREAM = broker.queue_name
GROUP = broker.consumer_group_name

# Reclaim counters expire long after the poison ceiling can be hit in
# consecutive passes; a task re-added this long ago is a fresh message.
_RECLAIM_TTL_SECONDS = 24 * 3600
_BATCH = 100

__all__ = ["reap_pending_task"]


def _reclaim_key(task_id: str) -> str:
    return f"bigbug:reaper:reclaims:{task_id}"


async def reap_pending(redis: Redis, *, poison_max_reclaims: int | None = None) -> int:
    """One reaper pass: claim idle PEL entries, re-add + ack them.

    Returns the number of entries re-delivered. Poison entries (reclaimed
    more than the ceiling) are acked without re-adding, logged as ERROR and
    written to the notification outbox.
    """
    ceiling = (
        settings.reaper_poison_max_reclaims if poison_max_reclaims is None else poison_max_reclaims
    )
    claimed = 0
    poison: list[str] = []
    start_id = "0-0"
    while True:
        result = await redis.xautoclaim(
            STREAM,
            GROUP,
            "reaper",
            min_idle_time=settings.task_idle_timeout_ms,
            start_id=start_id,
            count=_BATCH,
        )
        # XAUTOCLAIM reply: [next_cursor, [(id, fields), ...], [deleted_ids]]
        entries = result[1]
        if not entries:
            break
        for entry_id, fields in entries:
            task_id = await _redeliver(redis, fields, ceiling, poison)
            if task_id is not None:
                claimed += 1
            await redis.xack(STREAM, GROUP, entry_id)
        next_cursor = result[0]
        if not next_cursor or next_cursor == "0-0":
            break
        start_id = next_cursor

    await _log_pass(redis, claimed, poison)
    if poison:
        for entry in poison:
            logger.error(
                "reaper: task %s exceeded reclaim ceiling (%d) — poison entry, "
                "acked without re-delivery; outbox event written",
                entry,
                ceiling,
            )
        await _write_poison_events(poison)
    return claimed


async def _redeliver(
    redis: Redis, fields: dict[bytes, bytes], ceiling: int, poison: list[str]
) -> str | None:
    """Re-add one claimed entry to the stream; None when it hit the ceiling.

    The caller acks the old entry either way — re-add first, then ack, so a
    crash in between costs a duplicate delivery (at-least-once), never a
    lost task.
    """
    task_id, task_name = _parse_task(fields)
    count = await redis.incr(_reclaim_key(task_id))
    await redis.expire(_reclaim_key(task_id), _RECLAIM_TTL_SECONDS)
    if count > ceiling:
        poison.append(f"{task_name}:{task_id}")
        return None
    await redis.xadd(STREAM, fields)
    logger.info("reaper re-delivered task %s (%s), reclaim #%d", task_name, task_id, count)
    return task_id


def _parse_task(fields: dict[bytes, bytes]) -> tuple[str, str]:
    raw = fields.get(b"data")
    if raw:
        try:
            msg = json.loads(raw)
            return str(msg.get("task_id", "unknown")), str(msg.get("task_name", "unknown"))
        except ValueError, TypeError:
            pass
    return "unknown", "unknown"


async def _log_pass(redis: Redis, claimed: int, poison: list[str]) -> None:
    """Observability line per pass (issue #116: logs now, metrics later)."""
    xlen = await redis.xlen(STREAM)
    summary = await redis.xpending(STREAM, GROUP)
    pel_size = summary.get("pending", 0) if summary else 0
    oldest = summary.get("oldest") if summary else None
    # redis-py returns the oldest entry as (id, consumer, idle_ms, deliveries)
    oldest_age_ms = oldest[2] if oldest else 0
    logger.info(
        "reaper pass: stream_len=%d pel_size=%d oldest_pending_ms=%s reclaimed=%d poison=%s",
        xlen,
        pel_size,
        oldest_age_ms,
        claimed,
        poison or "[]",
    )


async def _write_poison_events(poison: list[str]) -> None:
    """Persist poison entries as outbox events (console story surfaces them)."""
    from sqlalchemy.exc import IntegrityError

    from app.models.notification_outbox import NotificationOutbox

    for entry in poison:
        try:
            async with AsyncSessionLocal() as db:
                db.add(
                    NotificationOutbox(
                        dedup_key=f"reaper:poison:{entry}",
                        event_type="task_reap_poison",
                        payload={"task": entry, "reclaims_exceeded": True},
                    )
                )
                await db.commit()
        except IntegrityError:
            logger.debug("poison event for %s already written", entry)
        except Exception:
            logger.exception("failed to write poison event for %s", entry)


@broker.task(**_TASK_LABELS)
async def reap_pending_task() -> int:
    """Claim idle PEL entries and re-deliver them (cron pass body)."""

    async def _body() -> int:
        redis = _get_client(settings.redis_url)
        return await reap_pending(redis)

    return await run_tracked("reap_pending_task", _body, payload={"args": [], "kwargs": {}})
