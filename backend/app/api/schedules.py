from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_viewer
from app.database import get_db
from app.models.build_schedule import BuildSchedule
from app.models.sync_schedule import SyncSchedule
from app.schemas.image import BuildScheduleOut
from app.schemas.mirror import SyncScheduleOut

router = APIRouter()


@router.get("/sync", response_model=list[SyncScheduleOut])
async def list_sync_schedules(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(select(SyncSchedule))
    return result.scalars().all()


@router.get("/build", response_model=list[BuildScheduleOut])
async def list_build_schedules(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(select(BuildSchedule))
    return result.scalars().all()
