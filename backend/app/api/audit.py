"""Audit log API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.audit import AuditLogList
from app.services.audit import AuditService

router = APIRouter()


@router.get("/", response_model=AuditLogList)
async def get_audit_logs(
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users:read")),
):
    items, total = await AuditService.get_logs(
        db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return AuditLogList(items=items, total=total)
