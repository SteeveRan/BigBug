from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import require_permission
from app.database import get_db
from app.models.helm_chart_source import HelmChartSource
from app.models.helm_chart_version import HelmChartVersion
from app.models.helm_sync_log import HelmSyncLog
from app.models.sync_schedule import SyncSchedule
from app.schemas.helm import (
    CreateHelmChartSourceRequest,
    CreateHelmSyncScheduleRequest,
    HelmChartSourceDetailOut,
    HelmChartSourceOut,
    HelmChartVersionOut,
    HelmSyncLogOut,
    HelmSyncScheduleOut,
    UpdateHelmChartSourceRequest,
    UpdateHelmSyncScheduleRequest,
)

router = APIRouter()


# ──── Sources CRUD ────────────────────────────────────────────────────────


@router.get("", response_model=list[HelmChartSourceOut])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:read")),
):
    result = await db.execute(select(HelmChartSource))
    return result.scalars().all()


@router.get("/{source_id}", response_model=HelmChartSourceDetailOut)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:read")),
):
    result = await db.execute(
        select(HelmChartSource)
        .options(selectinload(HelmChartSource.versions))
        .where(HelmChartSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Helm chart source not found"
        )
    return source


@router.post("", response_model=HelmChartSourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    data: CreateHelmChartSourceRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:write")),
):
    from app.services.helm import helm_service

    source = await helm_service.import_source_from_url(
        data.name,
        data.repo_url,
        db,
        provider_id=data.provider_id,
        target_repo_url=data.target_repo_url,
    )
    return source


@router.patch("/{source_id}", response_model=HelmChartSourceOut)
async def update_source(
    source_id: int,
    data: UpdateHelmChartSourceRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:write")),
):
    result = await db.execute(select(HelmChartSource).where(HelmChartSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Helm chart source not found"
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(source, field, value)

    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:delete")),
):
    result = await db.execute(select(HelmChartSource).where(HelmChartSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Helm chart source not found"
        )
    await db.delete(source)
    await db.commit()


# ──── Index / Sync ─────────────────────────────────────────────────────────


@router.post("/{source_id}/index", response_model=HelmSyncLogOut)
async def index_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:index")),
):
    """Re-index a Helm chart source (fetch index.yaml and update versions)."""
    result = await db.execute(select(HelmChartSource).where(HelmChartSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Helm chart source not found"
        )

    from app.services.helm import helm_service

    sync_log = await helm_service.refresh_source(source, db)
    await db.commit()
    await db.refresh(sync_log)
    return sync_log


# ──── Mirror ────────────────────────────────────────────────────────────────


@router.post("/{source_id}/mirror", response_model=HelmSyncLogOut)
async def mirror_chart(
    source_id: int,
    chart_name: str = Query(..., description="Chart name to mirror"),
    version: str = Query(..., description="Chart version to mirror"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("helm:sync")),
) -> HelmSyncLog:
    """Mirror one Helm chart version into the target repository.

    Triggers a GitLab CI pipeline (helm-sync-template) which performs the
    actual copy. ``is_synced`` on the version is only set once the webhook
    reports the pipeline succeeded.
    """
    source = await db.get(HelmChartSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Helm chart source not found"
        )

    if not source.gitlab_project_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source has no GitLab project configured for mirroring.",
        )

    from app.services.helm import helm_service

    log = await helm_service.mirror_chart(
        source=source,
        chart_name=chart_name,
        version=version,
        db=db,
        triggered_by=f"user:{current_user.username}",
    )
    await db.commit()
    await db.refresh(log)
    return log


# ──── Versions ─────────────────────────────────────────────────────────────


@router.get("/{source_id}/versions", response_model=list[HelmChartVersionOut])
async def list_versions(
    source_id: int,
    chart_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:read")),
):
    """List chart versions for a source. Optionally filter by chart_name."""
    stmt = (
        select(HelmChartVersion)
        .where(HelmChartVersion.source_id == source_id)
        .order_by(
            HelmChartVersion.chart_name,
            HelmChartVersion.version.desc(),
        )
    )
    if chart_name:
        stmt = stmt.where(HelmChartVersion.chart_name == chart_name)

    result = await db.execute(stmt)
    return result.scalars().all()


# ──── Sync Logs ────────────────────────────────────────────────────────────


@router.get("/{source_id}/logs", response_model=list[HelmSyncLogOut])
async def get_sync_logs(
    source_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:read")),
):
    result = await db.execute(
        select(HelmSyncLog)
        .where(HelmSyncLog.source_id == source_id)
        .order_by(HelmSyncLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


# ──── Sync Schedule ─────────────────────────────────────────────────────────


@router.get("/{source_id}/schedule", response_model=list[HelmSyncScheduleOut])
async def get_helm_sync_schedules(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:read")),
):
    """Get all sync schedules for a Helm chart source."""
    source = await db.get(HelmChartSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Helm chart source not found"
        )

    result = await db.execute(
        select(SyncSchedule).where(
            SyncSchedule.sync_type == "helm_chart",
            SyncSchedule.helm_chart_source_id == source_id,
        )
    )
    return result.scalars().all()


@router.post(
    "/{source_id}/schedule",
    response_model=HelmSyncScheduleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_helm_sync_schedule(
    source_id: int,
    data: CreateHelmSyncScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:write")),
):
    """Create a sync schedule for a Helm chart source."""
    source = await db.get(HelmChartSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Helm chart source not found"
        )

    schedule = SyncSchedule(
        sync_type="helm_chart",
        helm_chart_source_id=source_id,
        cron_expression=data.cron_expression,
        is_enabled=data.is_enabled,
        use_default_schedule=data.use_default_schedule,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.patch("/{source_id}/schedule/{schedule_id}", response_model=HelmSyncScheduleOut)
async def update_helm_sync_schedule(
    source_id: int,
    schedule_id: int,
    data: UpdateHelmSyncScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:write")),
):
    """Update a sync schedule."""
    result = await db.execute(
        select(SyncSchedule).where(
            SyncSchedule.id == schedule_id,
            SyncSchedule.sync_type == "helm_chart",
            SyncSchedule.helm_chart_source_id == source_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync schedule not found",
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(schedule, field, value)

    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.delete("/{source_id}/schedule/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_helm_sync_schedule(
    source_id: int,
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("helm:delete")),
):
    """Delete a sync schedule."""
    result = await db.execute(
        select(SyncSchedule).where(
            SyncSchedule.id == schedule_id,
            SyncSchedule.sync_type == "helm_chart",
            SyncSchedule.helm_chart_source_id == source_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync schedule not found",
        )

    await db.delete(schedule)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
