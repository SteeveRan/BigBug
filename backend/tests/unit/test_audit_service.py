"""
@file test_audit_service.py
@description Unit tests for AuditService — log_event() and get_logs()
             with filtering and pagination.
@dependencies pytest, pytest-asyncio, backend/tests/conftest.py
@relatedFiles ../../app/services/audit.py, ../../app/models/audit_log.py
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.services.audit import AuditService

# ──────────────────────────────────────────────────────────────────────
# log_event
# ──────────────────────────────────────────────────────────────────────


class TestAuditServiceLogEvent:
    """Tests for AuditService.log_event()"""

    @pytest.mark.asyncio
    async def test_log_event_success(self, db_session: AsyncSession):
        """log_event creates audit log entry in database."""
        await AuditService.log_event(
            db_session,
            user_id=1,
            username="testadmin",
            action="login",
            resource_type="auth",
        )

        result = await db_session.execute(select(AuditLog))
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].username == "testadmin"
        assert logs[0].action == "login"
        assert logs[0].resource_type == "auth"
        assert logs[0].user_id == 1

    @pytest.mark.asyncio
    async def test_log_event_never_raises(self, db_session: AsyncSession):
        """log_event never raises exceptions even if DB commit fails."""
        with patch.object(db_session, "commit", side_effect=RuntimeError("DB down")):
            # Should not raise
            await AuditService.log_event(
                db_session,
                user_id=1,
                username="testadmin",
                action="login",
                resource_type="auth",
            )
        # Test passes if no exception was raised

    @pytest.mark.asyncio
    async def test_log_event_with_all_fields(self, db_session: AsyncSession):
        """log_event stores all provided fields."""
        await AuditService.log_event(
            db_session,
            user_id=42,
            username="operator1",
            action="update",
            resource_type="mirror",
            resource_id=15,
            resource_name="my-mirror",
            details={"changed_fields": ["url"]},
            ip_address="192.168.1.100",
        )

        result = await db_session.execute(select(AuditLog).where(AuditLog.action == "update"))
        log = result.scalar_one()
        assert log.user_id == 42
        assert log.username == "operator1"
        assert log.resource_type == "mirror"
        assert log.resource_id == 15
        assert log.resource_name == "my-mirror"
        assert log.details == {"changed_fields": ["url"]}
        assert log.ip_address == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_log_event_with_minimal_fields(self, db_session: AsyncSession):
        """log_event works with only required fields."""
        await AuditService.log_event(
            db_session,
            user_id=None,
            username="system",
            action="sync",
            resource_type="helm_source",
        )

        result = await db_session.execute(select(AuditLog))
        log = result.scalar_one()
        assert log.username == "system"
        assert log.action == "sync"
        assert log.resource_type == "helm_source"
        assert log.user_id is None
        assert log.resource_id is None
        assert log.resource_name is None
        assert log.details is None
        assert log.ip_address is None


# ──────────────────────────────────────────────────────────────────────
# get_logs
# ──────────────────────────────────────────────────────────────────────


class TestAuditServiceGetLogs:
    """Tests for AuditService.get_logs()"""

    async def _seed_logs(self, db_session: AsyncSession) -> None:
        """Create 5 audit log entries for pagination/filtering tests."""
        logs = [
            AuditLog(
                user_id=1,
                username="admin",
                action="login",
                resource_type="auth",
                created_at=datetime.now(UTC) - timedelta(hours=i),
            )
            for i in range(5)
        ]
        logs[1].action = "update"
        logs[1].resource_type = "mirror"
        logs[1].resource_name = "mirror-1"
        logs[2].action = "create"
        logs[2].resource_type = "mirror"
        logs[2].resource_name = "mirror-2"
        logs[3].action = "delete"
        logs[3].resource_type = "helm_source"
        logs[3].resource_name = "helm-1"
        # logs[4] stays as login/auth

        db_session.add_all(logs)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_get_logs_returns_all(self, db_session: AsyncSession):
        """get_logs returns all logs when no filters."""
        await self._seed_logs(db_session)
        items, total = await AuditService.get_logs(db_session)
        assert total == 5
        assert len(items) == 5

    @pytest.mark.asyncio
    async def test_get_logs_filter_by_action(self, db_session: AsyncSession):
        """get_logs filters by action correctly."""
        await self._seed_logs(db_session)
        items, total = await AuditService.get_logs(db_session, action="update")
        assert total == 1
        assert len(items) == 1
        assert items[0].action == "update"

    @pytest.mark.asyncio
    async def test_get_logs_filter_by_resource_type(self, db_session: AsyncSession):
        """get_logs filters by resource_type correctly."""
        await self._seed_logs(db_session)
        items, total = await AuditService.get_logs(db_session, resource_type="mirror")
        assert total == 2
        assert len(items) == 2
        resource_types = {item.resource_type for item in items}
        assert resource_types == {"mirror"}

    @pytest.mark.asyncio
    async def test_get_logs_pagination(self, db_session: AsyncSession):
        """get_logs respects page and page_size."""
        await self._seed_logs(db_session)
        items, total = await AuditService.get_logs(db_session, page=1, page_size=2)
        assert total == 5  # total is independent of page
        assert len(items) == 2

        items_page2, _ = await AuditService.get_logs(db_session, page=2, page_size=2)
        assert len(items_page2) == 2

        items_page3, _ = await AuditService.get_logs(db_session, page=3, page_size=2)
        assert len(items_page3) == 1

    @pytest.mark.asyncio
    async def test_get_logs_returns_total_count(self, db_session: AsyncSession):
        """get_logs returns correct total count independent of page."""
        await self._seed_logs(db_session)
        _, total = await AuditService.get_logs(db_session, page=1, page_size=2)
        assert total == 5

    @pytest.mark.asyncio
    async def test_get_logs_filter_by_date_range(self, db_session: AsyncSession):
        """get_logs filters by date_from and date_to."""
        await self._seed_logs(db_session)
        date_from = datetime.now(UTC) - timedelta(hours=2, minutes=30)
        date_to = datetime.now(UTC) - timedelta(minutes=30)
        items, total = await AuditService.get_logs(db_session, date_from=date_from, date_to=date_to)
        # Should only include logs created between 0.5h and 2.5h ago
        # (Skipping the most recent and oldest)
        assert total >= 2  # logs[1] and logs[2]

    @pytest.mark.asyncio
    async def test_get_logs_empty_result(self, db_session: AsyncSession):
        """get_logs returns empty list and zero total when no logs match."""
        await self._seed_logs(db_session)
        items, total = await AuditService.get_logs(db_session, action="nonexistent")
        assert total == 0
        assert items == []

    @pytest.mark.asyncio
    async def test_get_logs_ordered_by_created_at_desc(self, db_session: AsyncSession):
        """get_logs returns logs ordered by created_at descending (most recent first)."""
        await self._seed_logs(db_session)
        items, _ = await AuditService.get_logs(db_session, page_size=5)
        # Verify descending order: most recent first
        for i in range(len(items) - 1):
            assert items[i].created_at >= items[i + 1].created_at
