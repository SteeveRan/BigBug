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

import os
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

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
    """Write an outbox event for reliable notification delivery.

    shortcut: stub — no outbox table yet; Phase 3 adds storage + sender
    (ADR-0039 non-goal until then).
    """
    raise NotImplementedError("outbox storage and sender land in Phase 3 (ADR-0039)")


async def reconcile(db: AsyncSession, key: str) -> None:
    """Detect external drift for item *key* and repair it via re-push.

    shortcut: scaffolding only — drift detection (external state vs DB) lands
    in Phase 3 (ADR-0039).
    """
    raise NotImplementedError("reconciliation lands in Phase 3 (ADR-0039)")
