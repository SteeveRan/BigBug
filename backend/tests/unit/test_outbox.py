"""
@file test_outbox.py
@description Unit tests for the transactional outbox (ADR-0039 Phase 3,
             issue #111): dedup on write, sender idempotency under
             redelivery, and the crash matrix for outbox+commit.
@dependencies pytest, sqlalchemy
@relatedFiles ../../app/services/sync_engine.py, ../../app/tasks/outbox_tasks.py
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select

from app.models.notification_outbox import NotificationOutbox
from app.services import sync_engine


async def _write(db, key: str, event_type: str = "reconciliation.drift") -> None:
    await sync_engine.outbox_write(db, event_type, {"dedup_key": key, "x": 1})


class TestOutboxWrite:
    async def test_write_creates_row(self, db_session):
        await _write(db_session, "k1")
        rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
        assert len(rows) == 1
        assert rows[0].dedup_key == "k1"
        assert rows[0].sent_at is None
        assert rows[0].payload == {"dedup_key": "k1", "x": 1}

    async def test_same_key_twice_one_row(self, db_session):
        """Dedup: same dedup_key written twice → exactly one row."""
        await _write(db_session, "dup")
        await _write(db_session, "dup")
        count = (
            await db_session.execute(select(func.count()).select_from(NotificationOutbox))
        ).scalar_one()
        assert count == 1

    async def test_different_keys_two_rows(self, db_session):
        await _write(db_session, "a")
        await _write(db_session, "b")
        count = (
            await db_session.execute(select(func.count()).select_from(NotificationOutbox))
        ).scalar_one()
        assert count == 2

    async def test_missing_dedup_key_raises(self, db_session):
        import pytest

        with pytest.raises(ValueError, match="dedup_key"):
            await sync_engine.outbox_write(db_session, "evt", {})


class TestOutboxSender:
    async def test_sender_delivers_and_marks_sent(self, db_session):
        await _write(db_session, "s1")
        await db_session.commit()

        with (
            patch("app.tasks.outbox_tasks.AsyncSessionLocal", return_value=_ctx(db_session)),
            patch("app.services.audit.AuditService.log_event", new_callable=AsyncMock),
        ):
            from app.tasks.outbox_tasks import send_pending_outbox_task

            delivered = await send_pending_outbox_task()

        assert delivered == 1
        rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
        assert rows[0].sent_at is not None

    async def test_sender_idempotent_under_redelivery(self, db_session):
        """Second run (task redelivery / crash after sent-marking) delivers
        nothing new — sent_at filter skips already-sent rows."""
        await _write(db_session, "s2")
        await db_session.commit()

        with (
            patch("app.tasks.outbox_tasks.AsyncSessionLocal", return_value=_ctx(db_session)),
            patch("app.services.audit.AuditService.log_event", new_callable=AsyncMock),
        ):
            from app.tasks.outbox_tasks import send_pending_outbox_task

            assert await send_pending_outbox_task() == 1
            assert await send_pending_outbox_task() == 0

    async def test_sender_writes_audit_event(self, db_session):
        """Delivery effect = audit-log event (in-app sink)."""
        await _write(db_session, "s3", event_type="reconciliation.drift")
        await db_session.commit()

        with (
            patch("app.tasks.outbox_tasks.AsyncSessionLocal", return_value=_ctx(db_session)),
            patch("app.services.audit.AuditService.log_event", new_callable=AsyncMock) as mock_log,
        ):
            from app.tasks.outbox_tasks import send_pending_outbox_task

            await send_pending_outbox_task()

        mock_log.assert_awaited_once()
        assert mock_log.await_args.kwargs["action"] == "reconciliation.drift"


class _Ctx:
    """Async context manager standing in for AsyncSessionLocal()."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc):
        return False


def _ctx(session):
    return _Ctx(session)


# ---------------------------------------------------------------------------
# Chaos: crash matrix for outbox + commit (issue #111 acceptance criteria)
# ---------------------------------------------------------------------------


class TestOutboxCrashMatrix:
    async def test_crash_after_outbox_write_before_commit_no_row(self, db_session):
        """Kill between outbox_write and the commit: the row was never
        committed — a fresh session sees nothing → no duplicate ever."""

        async def _apply(session):
            await _write(session, "c1")

        with patch("app.services.sync_engine._crash_point") as mock_crash:
            mock_crash.side_effect = lambda name: (
                (_ for _ in ()).throw(sync_engine.CrashInjectedError(name))
                if name == "commit:before"
                else None
            )
            import pytest

            with pytest.raises(sync_engine.CrashInjectedError):
                await sync_engine.commit_cursor(db_session, "item", _apply)

        await db_session.rollback()
        count = (
            await db_session.execute(select(func.count()).select_from(NotificationOutbox))
        ).scalar_one()
        assert count == 0

    async def test_crash_after_commit_row_survives_and_sender_no_dupes(self, db_session):
        """Kill after commit: the row survives (at-least-once) and the sender
        marks it sent exactly once — no duplicate notifications."""

        async def _apply(session):
            await _write(session, "c2")

        with patch("app.services.sync_engine._crash_point") as mock_crash:
            mock_crash.side_effect = lambda name: (
                (_ for _ in ()).throw(sync_engine.CrashInjectedError(name))
                if name == "commit:after"
                else None
            )
            import pytest

            with pytest.raises(sync_engine.CrashInjectedError):
                await sync_engine.commit_cursor(db_session, "item", _apply)

        # Fresh session = what a restarted worker sees: the row is there.
        rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
        assert len(rows) == 1
        assert rows[0].sent_at is None

        with (
            patch("app.tasks.outbox_tasks.AsyncSessionLocal", return_value=_ctx(db_session)),
            patch("app.services.audit.AuditService.log_event", new_callable=AsyncMock),
        ):
            from app.tasks.outbox_tasks import send_pending_outbox_task

            assert await send_pending_outbox_task() == 1
            assert await send_pending_outbox_task() == 0  # redelivery no-op

        # Exactly one notification row despite the crash + redelivery.
        count = (
            await db_session.execute(select(func.count()).select_from(NotificationOutbox))
        ).scalar_one()
        assert count == 1
        assert rows[0].sent_at is not None
        assert datetime.now(UTC) > rows[0].sent_at
