"""Maintenance mode API (issue #114).

Admin toggle (``system:config``, audit per ADR-0026) and a public minimal
status endpoint for the UI banner. The flag itself lives in platform_settings;
enforcement is in the schedulers (skip enqueue passes). Scaling workers to 0
is a manual runbook step (docs/runbooks/maintenance-mode.md).
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.database import get_db
from app.models.user import User
from app.services.audit import AuditService
from app.services.platform_settings import (
    MAINTENANCE_KEY,
    get_setting,
    set_setting,
)

logger = logging.getLogger(__name__)

router = APIRouter()  # admin: /api/admin/maintenance
public_router = APIRouter()  # unauthenticated: /api/status/maintenance


class MaintenanceOut(BaseModel):
    maintenance_mode: bool


class MaintenanceUpdate(BaseModel):
    maintenance_mode: bool


@router.get("/maintenance", response_model=MaintenanceOut, tags=["admin"])
async def get_maintenance(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("system:config")),
):
    """Current maintenance-mode flag."""
    return MaintenanceOut(maintenance_mode=bool(await get_setting(db, MAINTENANCE_KEY, False)))


@router.patch("/maintenance", response_model=MaintenanceOut, tags=["admin"])
async def update_maintenance(
    data: MaintenanceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system:config")),
):
    """Toggle maintenance mode; writes an audit event (ADR-0026)."""
    await set_setting(db, MAINTENANCE_KEY, data.maintenance_mode)
    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="update",
        resource_type="platform_settings",
        resource_name=MAINTENANCE_KEY,
        details={"maintenance_mode": data.maintenance_mode},
        ip_address=request.client.host if request.client else None,
    )
    logger.info("Maintenance mode set to %s by %s", data.maintenance_mode, current_user.username)
    return MaintenanceOut(maintenance_mode=data.maintenance_mode)


@public_router.get("/maintenance", response_model=MaintenanceOut)
async def get_maintenance_status(db: AsyncSession = Depends(get_db)):
    """Public, unauthenticated banner endpoint (issue #114). Reads the flag
    directly (no scheduler TTL cache) via the request session."""
    return MaintenanceOut(maintenance_mode=bool(await get_setting(db, MAINTENANCE_KEY, False)))
