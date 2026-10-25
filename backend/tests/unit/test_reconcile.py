"""
@file test_reconcile.py
@description Unit tests for the reconciliation surface (ADR-0039 Phase 3,
             issue #111): SchedulerService cron job (enqueue-only + pass
             lock), admin manual trigger endpoint, and the reconciliation
             service pass over synced docker tags.
@dependencies pytest, unittest.mock, sqlalchemy
@relatedFiles ../../app/services/scheduler.py, ../../app/api/admin.py,
              ../../app/services/reconciliation.py, ../../app/tasks/reconcile_tasks.py
"""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.scheduler import scheduler_service


class TestReconcileCronJob:
    @contextlib.asynccontextmanager
    async def _locked(self):
        yield True

    async def test_reconcile_job_enqueues_task(self):
        """_run_reconcile_job takes the pass lock and enqueues reconcile_all_task."""
        with (
            patch(
                "app.services.scheduler.job_pass_lock",
                return_value=contextlib.nullcontext(enter_result=True),
            ) as mock_lock,
            patch("app.services.scheduler.reconcile_all_task") as mock_task,
            patch("app.services.scheduler.enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            await scheduler_service._run_reconcile_job()

        mock_lock.assert_called_once_with("reconcile")
        mock_enqueue.assert_awaited_once_with(mock_task)

    async def test_reconcile_job_lock_skip_no_enqueue(self):
        with (
            patch(
                "app.services.scheduler.job_pass_lock",
                return_value=contextlib.nullcontext(enter_result=False),
            ),
            patch("app.services.scheduler.enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            await scheduler_service._run_reconcile_job()

        mock_enqueue.assert_not_awaited()

    async def test_start_registers_reconcile_cron(self):
        """start() registers the reconcile cron job from settings."""
        scheduler_service.scheduler = MagicMock()
        try:
            with patch("app.config.settings.reconcile_cron", "0 4 * * *"):
                await scheduler_service.start()
        finally:
            await scheduler_service.stop()

        job_ids = [c.kwargs.get("id") for c in scheduler_service.scheduler.add_job.call_args_list]
        assert "reconcile" in job_ids


class TestReconcileEndpoint:
    async def test_manual_reconcile_enqueues_all(self, client, login_headers):
        with (
            patch("app.tasks.reconcile_tasks.reconcile_all_task") as mock_task,
            patch("app.tasks.enqueue.enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            response = await client.post("/api/admin/reconcile", headers=login_headers)

        assert response.status_code == 200
        assert response.json() == {"enqueued": "reconcile_all_task"}
        mock_enqueue.assert_awaited_once_with(mock_task)

    async def test_manual_reconcile_single_source(self, client, login_headers):
        with (
            patch("app.tasks.reconcile_tasks.reconcile_docker_source_task") as mock_task,
            patch("app.tasks.enqueue.enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            response = await client.post("/api/admin/reconcile?source_id=7", headers=login_headers)

        assert response.status_code == 200
        assert response.json() == {
            "enqueued": "reconcile_docker_source_task",
            "source_id": 7,
        }
        mock_enqueue.assert_awaited_once_with(mock_task, 7)

    async def test_manual_reconcile_requires_permission(self, client, viewer_token):
        response = await client.post(
            "/api/admin/reconcile",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert response.status_code == 403
