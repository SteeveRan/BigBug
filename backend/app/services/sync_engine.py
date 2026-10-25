"""Sync engine core — the hand-reviewed convergence kernel (ADR-0039, guardrail 1).

Convergence rule: external side effect first, DB commit second; both steps
idempotent. Delivery is at-least-once (taskiq + Redis Streams), so a crash or
duplicate run must converge state instead of corrupting it:

- crash before push  → nothing changed anywhere; plain re-run converges
- crash push→commit  → idempotent push (upsert-by-key) is a no-op on re-run;
  the not-yet-committed cursor is written by the re-run
- crash after commit → already converged; duplicate delivery is a no-op

HAND-REVIEWED CORE — do not let agents modify this module without human
review (Temporal-vs-DIY verdict, ADR-0039). Task bodies call the primitives
below; the primitives never call tasks. Imports are lint-banned
(guardrail 3): no network clients, clock, randomness, API layer, scheduler,
or broker in this file — task bodies may use them, the kernel may not.

Crash injection (chaos tests, issue #110): set ``BIGBUG_FAILPOINT`` to a
failpoint name — ``push:before``, ``push:after``, ``commit:before``,
``commit:after`` — optionally ``name#N`` for the Nth hit, to raise
:class:`CrashInjectedError` at that boundary. No-op in production (env unset).
"""

from __future__ import annotations

import contextlib
import logging
import os
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

__all__ = [
    "CrashInjectedError",
    "commit_cursor",
    "idempotent_push",
    "outbox_write",
    "reconcile",
]

_FAILPOINT_ENV = "BIGBUG_FAILPOINT"
_hits: dict[str, int] = defaultdict(int)
_active_spec: str | None = None


class CrashInjectedError(RuntimeError):
    """Raised at an activated failpoint — the chaos-test stand-in for kill -9."""


def _failpoint_hit(name: str) -> bool:
    """True when the activated failpoint matches this crash point.

    Spec format: ``name`` (fire on every hit) or ``name#N`` (fire on the Nth
    hit — for mid-batch crashes). Counters reset when the spec changes, so a
    re-run with a different (or no) spec starts counting from zero.
    """
    global _active_spec
    spec = os.getenv(_FAILPOINT_ENV, "")
    if spec != _active_spec:
        _active_spec = spec
        _hits.clear()
    target, _, nth = spec.partition("#")
    if target != name:
        return False
    _hits[name] += 1
    return _hits[name] == int(nth or "1")


def _crash_point(name: str) -> None:
    if _failpoint_hit(name):
        raise CrashInjectedError(f"failpoint {name!r} triggered")


async def idempotent_push(key: str, push: Callable[[], Awaitable[Any]]) -> Any:
    """Run the external side effect for item *key*.

    *push* must be an idempotent upsert-by-key against the external system
    (copy image tag by digest, create pipeline with fixed variables): pushing
    the same key twice converges instead of duplicating. Crash points wrap
    the push so chaos tests can kill the process on either side of it.
    """
    _crash_point("push:before")  # crash: nothing changed anywhere, re-run
    result = await push()
    _crash_point("push:after")  # crash: external done, DB not — re-push converges
    return result


async def commit_cursor(
    db: AsyncSession,
    key: str,
    apply: Callable[[AsyncSession], Awaitable[Any]],
) -> Any:
    """Apply and commit the per-item DB state (the cursor) for item *key*.

    Per-item commit: a crash mid-batch costs the remaining items only, not
    the whole batch (rework 10%, not 90%). *apply* must be an idempotent DB
    mutation — upsert or status-flag transition, never a blind insert — so a
    redelivered item rewrites identical state.
    """
    _crash_point("commit:before")  # crash: push may be done, cursor not committed
    result = await apply(db)
    await db.commit()
    _crash_point("commit:after")  # crash: state already converged, duplicate is a no-op
    return result


async def outbox_write(db: AsyncSession, event_type: str, payload: dict[str, Any]) -> None:
    """Write an outbox event in the CURRENT transaction (not committed here).

    Insert-or-skip on the unique ``dedup_key``: the caller derives a stable
    key (e.g. ``"reconcile:{group_id}:{mirror_id}:{reason}"``), so redelivery
    and crash-restarts never duplicate the event. Commit happens with the
    sync state via :func:`commit_cursor` — that atomicity is the whole point
    of the transactional outbox.

    Uses SQLite- and Postgres-compatible savepoint handling: a conflicting
    key raises IntegrityError on flush; we roll back to savepoint and skip.
    """
    from sqlalchemy.exc import IntegrityError

    from app.models.notification_outbox import NotificationOutbox

    dedup_key = str(payload.get("dedup_key") or "")
    if not dedup_key:
        raise ValueError("outbox_write payload must carry a non-empty 'dedup_key'")

    async with db.begin_nested():
        db.add(
            NotificationOutbox(
                dedup_key=dedup_key,
                event_type=event_type,
                payload=payload,
            )
        )
        with contextlib.suppress(IntegrityError):
            # Duplicate dedup_key — skip (idempotent). Savepoint rollback
            # keeps the outer transaction usable.
            await db.flush()


async def reconcile(
    db: AsyncSession,
    key: str,
    *,
    expected: str | None,
    actual: str | None,
    repair: Callable[[], Awaitable[Any]],
) -> str:
    """Detect external drift for item *key* and repair it via idempotent re-push.

    The drift catcher (ADR-0039 Phase 3): compare the DB cursor (*expected*,
    e.g. synced digest) against actual external state (*actual*, e.g. the
    registry-reported digest). Drift repair = idempotent re-push, which
    converges by construction.

    Returns the verdict: ``"ok"`` (converged), ``"missing"`` (external absent),
    ``"drift"`` (digests differ) — ``"drift"``/``"missing"`` trigger the
    repair push; the caller records the outbox event (network callers may not
    live in the kernel).
    """
    if actual is not None and actual == expected:
        return "ok"

    verdict = "missing" if actual is None else "drift"
    logger.warning("reconcile %s: %s (expected=%s actual=%s)", key, verdict, expected, actual)

    # Idempotent re-push converges; crash points wrap it like a normal push.
    await idempotent_push(f"reconcile:{key}", repair)
    return verdict
