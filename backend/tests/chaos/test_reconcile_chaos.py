"""
@file test_reconcile_chaos.py
@description Chaos/unit tests for the reconciliation primitive and its crash
              matrix (ADR-0039 Phase 3, issue #111): drift detection against
              a fake external registry, idempotent repair, outbox event on
              drift, and crash safety of outbox_write + commit_cursor.
@dependencies pytest, sqlalchemy
@relatedFiles ../../app/services/sync_engine.py, ./test_sync_engine_chaos.py
"""

import pytest
from sqlalchemy import select

from app.models.notification_outbox import NotificationOutbox
from app.services import sync_engine
from app.services.sync_engine import CrashInjectedError

from .conftest import FakeExternalRegistry

DIGEST = "sha256:aaa"


class TestReconcileDrift:
    """reconcile primitive: verdicts + idempotent repair."""

    async def test_no_drift_returns_ok(self, fake_registry):
        calls: list[str] = []

        async def _repair() -> None:
            calls.append("push")

        verdict = await sync_engine.reconcile(
            None, "nginx:latest", expected=DIGEST, actual=DIGEST, repair=_repair
        )
        assert verdict == "ok"
        assert calls == []

    async def test_missing_tag_detected_and_repaired(self, fake_registry):
        """The drift case: Harbor GC removed the tag. Repair = idempotent
        re-push; the fake registry converges."""
        fake_registry.push("nginx:latest", DIGEST)
        fake_registry.objects.pop("nginx:latest")  # external drift: tag gone

        async def _repair() -> None:
            fake_registry.push("nginx:latest", DIGEST)

        verdict = await sync_engine.reconcile(
            None, "nginx:latest", expected=DIGEST, actual=None, repair=_repair
        )
        assert verdict == "missing"
        assert fake_registry.get("nginx:latest") == DIGEST

    async def test_digest_drift_detected_and_repaired(self, fake_registry):
        """Upstream force-push: external digest differs from the DB cursor."""
        fake_registry.push("nginx:latest", "sha256:evil")

        async def _repair() -> None:
            fake_registry.push("nginx:latest", DIGEST)

        verdict = await sync_engine.reconcile(
            None, "nginx:latest", expected=DIGEST, actual="sha256:evil", repair=_repair
        )
        assert verdict == "drift"
        assert fake_registry.get("nginx:latest") == DIGEST


class TestReconcileCrashMatrix:
    async def test_crash_during_repair_push_converges_on_rerun(
        self, db_session, fake_registry, failpoint
    ):
        """Kill mid-repair-push: nothing converged; re-run repairs."""
        fake_registry.push("nginx:latest", "sha256:evil")
        failpoint("push:before")
        with pytest.raises(CrashInjectedError):
            await sync_engine.reconcile(
                db_session,
                "nginx:latest",
                expected=DIGEST,
                actual="sha256:evil",
                repair=lambda: _push(fake_registry),
            )

        failpoint(None)
        verdict = await sync_engine.reconcile(
            db_session,
            "nginx:latest",
            expected=DIGEST,
            actual="sha256:evil",
            repair=lambda: _push(fake_registry),
        )
        assert verdict == "drift"
        assert fake_registry.get("nginx:latest") == DIGEST


async def _push(registry: FakeExternalRegistry) -> bool:
    return registry.push("nginx:latest", DIGEST)


class TestOutboxCrashSafety:
    """Outbox in the commit_cursor transaction: crash never duplicates or
    loses a committed notification (issue #111 acceptance)."""

    async def test_write_and_commit_together(self, db_session):
        async def _apply(session):
            await sync_engine.outbox_write(session, "reconciliation.drift", {"dedup_key": "d1"})

        await sync_engine.commit_cursor(db_session, "item", _apply)
        rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
        assert len(rows) == 1
        assert rows[0].dedup_key == "d1"

    async def test_crash_before_commit_outbox_row_not_committed(self, db_session, failpoint):
        """commit:before crash discards the un-committed outbox row — the
        re-run writes it exactly once."""

        async def _apply(session):
            await sync_engine.outbox_write(session, "reconciliation.drift", {"dedup_key": "d2"})

        failpoint("commit:before")
        with pytest.raises(CrashInjectedError):
            await sync_engine.commit_cursor(db_session, "item", _apply)

        failpoint(None)
        await sync_engine.commit_cursor(db_session, "item", _apply)

        rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
        assert [r.dedup_key for r in rows] == ["d2"]

    async def test_redelivery_of_outbox_write_no_duplicate(self, db_session):
        """At-least-once redelivery replays outbox_write with the same key:
        the unique dedup_key collapses it to one row."""

        async def _pass(session):
            await sync_engine.outbox_write(session, "reconciliation.drift", {"dedup_key": "d3"})
            await sync_engine.outbox_write(session, "reconciliation.drift", {"dedup_key": "d3"})

        await sync_engine.commit_cursor(db_session, "item", _pass)
        rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
        assert len(rows) == 1
