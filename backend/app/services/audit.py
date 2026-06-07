"""Audit logging service."""

import logging
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    @staticmethod
    async def log_event(
        db: AsyncSession,
        *,
        user_id: int | None,
        username: str,
        action: str,
        resource_type: str,
        resource_id: int | None = None,
        resource_name: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log an audit event. Never raises exceptions."""
        try:
            log_entry = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                details=details,
                ip_address=ip_address,
                created_at=datetime.now(UTC),
            )
            db.add(log_entry)
            await db.commit()
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    @staticmethod
    async def get_logs(
        db: AsyncSession,
        *,
        user_id: int | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[AuditLog], int]:
        """Get audit logs with filtering and pagination."""
        filters: list = []
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if date_from:
            filters.append(AuditLog.created_at >= date_from)
        if date_to:
            filters.append(AuditLog.created_at <= date_to)

        count_query = select(func.count(AuditLog.id))
        if filters:
            count_query = count_query.where(and_(*filters))
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if filters:
            query = query.where(and_(*filters))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        items = list(result.scalars().all())

        return items, total
