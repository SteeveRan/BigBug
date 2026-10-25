"""
@file test_maintenance_mode.py
@description Tests for minimal maintenance mode (issue #114): platform_settings
              caching, scheduler pass gating (no enqueue, log-once), admin
              toggle API (permission + audit) and the public status endpoint.
@dependencies pytest, unittest.mock
@relatedFiles ../../app/api/maintenance.py, ../../app/services/platform_settings.py,
               ../../app/services/scheduler.py
"""

import contextlib
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.platform_setting import PlatformSetting
from app.services import platform_settings
from app.services.scheduler import scheduler_service


async def _set_flag(db, enabled: bool) -> None:
    """Write the flag directly (bypasses the service cache) and reset cache."""
    row = (
        await db.execute(select(PlatformSetting).where(PlatformSetting.key == "maintenance_mode"))
    ).scalar_one_or_none()
    if row is None:
        db.add(PlatformSetting(key="maintenance_mode", value=enabled))
    else:
        row.value = enabled
    await db.commit()
    platform_settings.invalidate_maintenance_cache()


class TestSettingsCaching:
    async def test_is_maintenance_mode_reads_db_and_caches(self):
        platform_settings.invalidate_maintenance_cache()
        with patch.object(
            platform_settings, "_read_maintenance_mode", AsyncMock(return_value=False)
        ) as mock_read:
            assert await platform_settings.is_maintenance_mode() is False
            # second call within TTL → no new DB read
            assert await platform_settings.is_maintenance_mode() is False
            mock_read.assert_awaited_once()
        # force refresh bypasses TTL
        with patch.object(
            platform_settings, "_read_maintenance_mode", AsyncMock(return_value=True)
        ):
            assert await platform_settings.is_maintenance_mode(force_refresh=True) is True

    async def test_read_fail_open(self):
        """DB outage during a scheduler-gate read → fail-open to False."""
        platform_settings.invalidate_maintenance_cache()

        class ExplodingSession:
            def __enter__(self):
                raise ConnectionError("db down")

            def __exit__(self, *exc):
                return False

        with patch("app.database.AsyncSessionLocal", ExplodingSession()):
            assert await platform_settings.is_maintenance_mode() is False

    async def test_set_setting_updates_and_invalidates(self, db_session):
        platform_settings.invalidate_maintenance_cache()
        await platform_settings.set_setting(db_session, "maintenance_mode", True)
        # new process view of the DB must be True even without force_refresh
        with patch.object(
            platform_settings, "_read_maintenance_mode", return_value=True
        ) as mock_read:
            assert await platform_settings.is_maintenance_mode() is True
        # cache was invalidated by set_setting → fresh read happened
        mock_read.assert_awaited_once()

    async def test_get_setting_default(self, db_session):
        assert await platform_settings.get_setting(db_session, "no_such_key", "dflt") == "dflt"


class TestSchedulerGate:
    async def test_pass_skips_enqueue_when_maintenance_on(self):
        platform_settings.invalidate_maintenance_cache()
        scheduler_service._maintenance_logged = False
        with (
            patch("app.services.scheduler.is_maintenance_mode", AsyncMock(return_value=True)),
            patch("app.services.scheduler.job_pass_lock") as mock_lock,
            patch("app.services.scheduler.enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            await scheduler_service._run_sync_jobs()

        mock_enqueue.assert_not_awaited()
        mock_lock.assert_not_called()  # gate fires before the pass lock

    async def test_pass_enqueues_when_maintenance_off(self):
        with (
            patch("app.services.scheduler.is_maintenance_mode", AsyncMock(return_value=False)),
            patch(
                "app.services.scheduler.job_pass_lock",
                return_value=contextlib.nullcontext(enter_result=True),
            ),
            patch("app.services.scheduler.enqueue", new_callable=AsyncMock) as mock_enqueue,
        ):
            await scheduler_service._run_sync_jobs()

        mock_enqueue.assert_awaited_once()

    async def test_gate_logs_once_per_transition(self, caplog):
        scheduler_service._maintenance_logged = False
        with patch("app.services.scheduler.is_maintenance_mode", AsyncMock(return_value=True)):
            assert await scheduler_service._gate_pass() is False
            assert await scheduler_service._gate_pass() is False
        warnings = [r for r in caplog.records if "Maintenance mode ON" in r.message]
        assert len(warnings) == 1

        with patch("app.services.scheduler.is_maintenance_mode", AsyncMock(return_value=False)):
            assert await scheduler_service._gate_pass() is True
        # flag reset → next ON logs again
        with patch("app.services.scheduler.is_maintenance_mode", AsyncMock(return_value=True)):
            await scheduler_service._gate_pass()
        warnings = [r for r in caplog.records if "Maintenance mode ON" in r.message]
        assert len(warnings) == 2
        scheduler_service._maintenance_logged = False


class TestAdminAPI:
    async def test_get_and_patch(self, client, db_session, login_headers):
        platform_settings.invalidate_maintenance_cache()
        resp = await client.get("/api/admin/maintenance", headers=login_headers)
        assert resp.status_code == 200
        assert resp.json() == {"maintenance_mode": False}

        resp = await client.patch(
            "/api/admin/maintenance", json={"maintenance_mode": True}, headers=login_headers
        )
        assert resp.status_code == 200
        assert resp.json() == {"maintenance_mode": True}

        # toggle is persisted and audit-logged
        row = (
            await db_session.execute(
                select(PlatformSetting).where(PlatformSetting.key == "maintenance_mode")
            )
        ).scalar_one()
        assert row.value is True
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.resource_type == "platform_settings")
        )
        events = result.scalars().all()
        assert len(events) == 1
        assert events[0].action == "update"

    async def test_requires_permission(self, client):
        assert (await client.get("/api/admin/maintenance")).status_code in (401, 403)
        assert (
            await client.patch("/api/admin/maintenance", json={"maintenance_mode": True})
        ).status_code in (401, 403)

    async def test_patch_clears_scheduler_cache(self, client, db_session, login_headers):
        platform_settings.invalidate_maintenance_cache()
        with patch.object(
            platform_settings, "_read_maintenance_mode", AsyncMock(return_value=True)
        ) as mock_read:
            await client.patch(
                "/api/admin/maintenance", json={"maintenance_mode": True}, headers=login_headers
            )
            # scheduler reads via its own session through the invalidated cache:
            # set_setting must have cleared it → a fresh DB read happens
            assert await platform_settings.is_maintenance_mode() is True
            mock_read.assert_awaited_once()


class TestPublicStatus:
    async def test_public_no_auth(self, client, db_session):
        await _set_flag(db_session, True)
        resp = await client.get("/api/status/maintenance")
        assert resp.status_code == 200
        assert resp.json() == {"maintenance_mode": True}
