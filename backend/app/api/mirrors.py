from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_operator, require_viewer
from app.database import get_db
from app.models.gitlab_mirror import GitlabMirror
from app.models.sync_log import SyncLog
from app.models.sync_schedule import SyncSchedule
from app.schemas.mirror import (
    CreateMirrorRequest,
    GitlabMirrorOut,
    ImportMirrorRequest,
    SyncLogOut,
    SyncScheduleOut,
    UpdateMirrorRequest,
    UpdateSyncScheduleRequest,
)

router = APIRouter()


@router.get("", response_model=list[GitlabMirrorOut])
async def list_mirrors(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(select(GitlabMirror))
    return result.scalars().all()


@router.get("/{mirror_id}", response_model=GitlabMirrorOut)
async def get_mirror(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(select(GitlabMirror).where(GitlabMirror.id == mirror_id))
    mirror = result.scalar_one_or_none()
    if not mirror:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mirror not found"
        )
    return mirror


@router.post("", response_model=GitlabMirrorOut, status_code=status.HTTP_201_CREATED)
async def create_mirror(
    data: CreateMirrorRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    mirror = GitlabMirror(
        project_id=data.project_id,
        gitlab_url=data.gitlab_url,
        mirrored_branch=data.mirrored_branch,
        pipeline_trigger_token=data.pipeline_trigger_token,
    )
    db.add(mirror)
    await db.flush()

    # Create default sync schedule
    schedule = SyncSchedule(
        mirror_id=mirror.id, is_enabled=True, use_default_schedule=True
    )
    db.add(schedule)

    await db.commit()
    await db.refresh(mirror)
    return mirror


@router.post(
    "/import", response_model=GitlabMirrorOut, status_code=status.HTTP_201_CREATED
)
async def import_mirror(
    data: ImportMirrorRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    from app.services.github import github_service
    from app.services.gitlab import gitlab_service

    project = await github_service.import_project_from_url(data.github_url, db)
    mirror = await gitlab_service.import_mirror_from_url(
        data.gitlab_url, project.id, db
    )
    return mirror


@router.patch("/{mirror_id}", response_model=GitlabMirrorOut)
async def update_mirror(
    mirror_id: int,
    data: UpdateMirrorRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(select(GitlabMirror).where(GitlabMirror.id == mirror_id))
    mirror = result.scalar_one_or_none()
    if not mirror:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mirror not found"
        )

    if data.mirrored_branch is not None:
        mirror.mirrored_branch = data.mirrored_branch
    if data.pipeline_trigger_token is not None:
        mirror.pipeline_trigger_token = data.pipeline_trigger_token

    await db.commit()
    await db.refresh(mirror)
    return mirror


@router.delete("/{mirror_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mirror(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(select(GitlabMirror).where(GitlabMirror.id == mirror_id))
    mirror = result.scalar_one_or_none()
    if not mirror:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mirror not found"
        )
    await db.delete(mirror)
    await db.commit()


@router.post("/{mirror_id}/sync", response_model=SyncLogOut)
async def trigger_sync(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    """Manually trigger a sync pipeline for this mirror."""
    result = await db.execute(select(GitlabMirror).where(GitlabMirror.id == mirror_id))
    mirror = result.scalar_one_or_none()
    if not mirror:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Mirror not found"
        )

    from app.services.gitlab import gitlab_service

    sync_log = await gitlab_service.trigger_sync(mirror, db, triggered_by="manual")
    return sync_log


@router.get("/{mirror_id}/logs", response_model=list[SyncLogOut])
async def get_sync_logs(
    mirror_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(SyncLog)
        .where(SyncLog.mirror_id == mirror_id)
        .order_by(SyncLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{mirror_id}/schedule", response_model=SyncScheduleOut)
async def get_sync_schedule(
    mirror_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(SyncSchedule).where(SyncSchedule.mirror_id == mirror_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
    return schedule


@router.patch("/{mirror_id}/schedule", response_model=SyncScheduleOut)
async def update_sync_schedule(
    mirror_id: int,
    data: UpdateSyncScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(
        select(SyncSchedule).where(SyncSchedule.mirror_id == mirror_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )

    if data.is_enabled is not None:
        schedule.is_enabled = data.is_enabled
    if data.use_default_schedule is not None:
        schedule.use_default_schedule = data.use_default_schedule
    if data.cron_expression is not None:
        schedule.cron_expression = data.cron_expression

    await db.commit()
    await db.refresh(schedule)
    return schedule
