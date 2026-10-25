"""
@file test_sync_run_api.py
@description Tests for the sync-runs admin API (issue #112): filters (status,
             stuck, entity), retry/requeue semantics (409 on wrong state,
             supersede on requeue, unknown task 409), permission gate, and
             audit events for every recovery action.
@dependencies pytest, sqlalchemy
@relatedFiles ../../app/api/sync_runs.py
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.sync_run import SyncRun


async def _mk_run(db, **kwargs) -> SyncRun:
    defaults = {
        "task_name": "sync_group_task",
        "entity_type": "sync_group",
        "entity_id": 1,
        "status": "failed",
        "attempts": 2,
        "max_attempts": 3,
        "payload": {"args": [1, 5], "kwargs": {}},
    }
    defaults.update(kwargs)
    run = SyncRun(**defaults)
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


class TestListSyncRuns:
    async def test_list_and_filters(self, client, db_session, login_headers):
        await _mk_run(db_session, status="failed")
        await _mk_run(
            db_session,
            task_name="cleanup_task",
            entity_type=None,
            entity_id=None,
            status="succeeded",
        )
        await _mk_run(
            db_session,
            status="running",
            heartbeat_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        await _mk_run(db_session, status="failed_permanent", attempts=3)

        resp = await client.get("/api/admin/sync-runs", headers=login_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 4

        resp = await client.get(
            "/api/admin/sync-runs", params={"run_status": "failed_permanent"}, headers=login_headers
        )
        assert [r["status"] for r in resp.json()] == ["failed_permanent"]

        resp = await client.get(
            "/api/admin/sync-runs", params={"entity_type": "sync_group"}, headers=login_headers
        )
        assert len(resp.json()) == 3

        resp = await client.get(
            "/api/admin/sync-runs", params={"stuck": True}, headers=login_headers
        )
        assert len(resp.json()) == 1
        assert resp.json()[0]["stuck"] is True

    async def test_requires_permission(self, client):
        resp = await client.get("/api/admin/sync-runs")
        assert resp.status_code in (401, 403)


class TestRetry:
    async def test_retry_failed_run_enqueues_via_helper(self, client, db_session, login_headers):
        run = await _mk_run(db_session, status="failed_permanent", attempts=3)

        with (
            patch("app.api.sync_runs.enqueue", new_callable=AsyncMock) as mock_enqueue,
            patch("app.api.sync_runs._resolve_task", return_value=MagicMock()),
        ):
            resp = await client.post(f"/api/admin/sync-runs/{run.id}/retry", headers=login_headers)

        assert resp.status_code == 200
        mock_enqueue.assert_awaited_once()
        assert mock_enqueue.await_args.args == (mock_enqueue.await_args.args[0], 1, 5)
        # old row untouched — a fresh queued run will be created by the wrapper
        await db_session.refresh(run)
        assert run.status == "failed_permanent"

    async def test_retry_non_recoverable_409(self, client, db_session, login_headers):
        run = await _mk_run(db_session, status="succeeded")
        resp = await client.post(f"/api/admin/sync-runs/{run.id}/retry", headers=login_headers)
        assert resp.status_code == 409

    async def test_retry_unknown_task_409(self, client, db_session, login_headers):
        run = await _mk_run(db_session, task_name="no_such_task")
        with patch("app.api.sync_runs._resolve_task", return_value=None):
            resp = await client.post(f"/api/admin/sync-runs/{run.id}/retry", headers=login_headers)
        assert resp.status_code == 409

    async def test_retry_writes_audit(self, client, db_session, login_headers):
        run = await _mk_run(db_session)
        with (
            patch("app.api.sync_runs.enqueue", new_callable=AsyncMock),
            patch("app.api.sync_runs._resolve_task", return_value=MagicMock()),
        ):
            await client.post(f"/api/admin/sync-runs/{run.id}/retry", headers=login_headers)
        events = (
            (await db_session.execute(select(AuditLog).where(AuditLog.resource_type == "sync_run")))
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert events[0].action == "retry"

    async def test_retry_all_failed(self, client, db_session, login_headers):
        await _mk_run(db_session, status="failed_permanent", attempts=3)
        await _mk_run(db_session, status="failed_permanent", attempts=3)
        await _mk_run(db_session, status="failed")  # not in DLQ

        with (
            patch("app.api.sync_runs.enqueue", new_callable=AsyncMock) as mock_enqueue,
            patch("app.api.sync_runs._resolve_task", return_value=MagicMock()),
        ):
            resp = await client.post("/api/admin/sync-runs/retry-all-failed", headers=login_headers)

        assert resp.status_code == 200
        assert resp.json() == {"retried": 2, "total_failed_permanent": 2}
        assert mock_enqueue.await_count == 2


class TestRequeue:
    async def test_requeue_stuck_marks_superseded(self, client, db_session, login_headers):
        run = await _mk_run(
            db_session,
            status="running",
            heartbeat_at=datetime.now(UTC) - timedelta(minutes=30),
        )
        with (
            patch("app.api.sync_runs.enqueue", new_callable=AsyncMock) as mock_enqueue,
            patch("app.api.sync_runs._resolve_task", return_value=MagicMock()),
        ):
            resp = await client.post(
                f"/api/admin/sync-runs/{run.id}/requeue", headers=login_headers
            )

        assert resp.status_code == 200
        assert resp.json()["status"] == "superseded"
        mock_enqueue.assert_awaited_once()
        await db_session.refresh(run)
        assert run.status == "superseded"

    async def test_requeue_fresh_running_409(self, client, db_session, login_headers):
        run = await _mk_run(db_session, status="running", heartbeat_at=datetime.now(UTC))
        resp = await client.post(f"/api/admin/sync-runs/{run.id}/requeue", headers=login_headers)
        assert resp.status_code == 409
