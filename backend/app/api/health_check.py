"""
@file health_check.py
@description REST API for health checks — system, sync group, and mirror level.
@dependencies app.services.health_check, app.core.rbac, app.schemas.health_check
@relatedFiles ../services/health_check.py, ../schemas/health_check.py
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_admin, require_permission
from app.database import get_db
from app.models.user import User
from app.schemas.health_check import HealthCheckReportOut
from app.services.health_check import HealthCheckService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/system", response_model=HealthCheckReportOut)
async def health_check_system(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin()),
):
    """Run a system-wide health check (admin only).

    Verifies:
    - All active credentials can be decrypted
    - All source providers are accessible
    - All sync groups have at least one mirror
    """
    report = await HealthCheckService.check_system(db)
    return HealthCheckReportOut(
        mirror_id=report.mirror_id,
        sync_group_id=report.sync_group_id,
        timestamp=report.timestamp,
        overall=report.overall,
        items=[
            {
                "component": item.component,
                "severity": item.severity,
                "message": item.message,
                "detail": item.detail,
            }
            for item in report.items
        ],
    )


@router.get("/sync-group/{sync_group_id}", response_model=HealthCheckReportOut)
async def health_check_sync_group(
    sync_group_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("sync_groups:read")),
):
    """Run a health check on a specific sync group and all its mirrors."""
    report = await HealthCheckService.check_sync_group(db, sync_group_id)
    return HealthCheckReportOut(
        mirror_id=report.mirror_id,
        sync_group_id=report.sync_group_id,
        timestamp=report.timestamp,
        overall=report.overall,
        items=[
            {
                "component": item.component,
                "severity": item.severity,
                "message": item.message,
                "detail": item.detail,
            }
            for item in report.items
        ],
    )


@router.get("/mirror/{mirror_id}", response_model=HealthCheckReportOut)
async def health_check_mirror(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("mirrors:read")),
):
    """Run a health check on a single mirror.

    Verifies credentials, source accessibility, and target existence.
    """
    report = await HealthCheckService.check_mirror(db, mirror_id)
    return HealthCheckReportOut(
        mirror_id=report.mirror_id,
        sync_group_id=report.sync_group_id,
        timestamp=report.timestamp,
        overall=report.overall,
        items=[
            {
                "component": item.component,
                "severity": item.severity,
                "message": item.message,
                "detail": item.detail,
            }
            for item in report.items
        ],
    )
