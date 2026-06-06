from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import require_operator, require_viewer
from app.database import get_db
from app.models.helm_chart_source import HelmChartSource
from app.models.helm_chart_version import HelmChartVersion
from app.models.helm_sync_log import HelmSyncLog
from app.schemas.helm import (
    CreateHelmChartSourceRequest,
    HelmChartSourceDetailOut,
    HelmChartSourceOut,
    HelmChartVersionOut,
    HelmSyncLogOut,
    UpdateHelmChartSourceRequest,
)

router = APIRouter()


# ──── Sources CRUD ────────────────────────────────────────────────────────


@router.get("", response_model=list[HelmChartSourceOut])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(select(HelmChartSource))
    return result.scalars().all()


@router.get("/{source_id}", response_model=HelmChartSourceDetailOut)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
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
    _=Depends(require_operator()),
):
    from app.services.helm import helm_service

    source = await helm_service.import_source_from_url(data.name, data.repo_url, db)
    return source


@router.patch("/{source_id}", response_model=HelmChartSourceOut)
async def update_source(
    source_id: int,
    data: UpdateHelmChartSourceRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(
        select(HelmChartSource).where(HelmChartSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Helm chart source not found"
        )

    if data.name is not None:
        source.name = data.name  # type: ignore[assignment]
    if data.repo_url is not None:
        source.repo_url = data.repo_url  # type: ignore[assignment]
    if data.description is not None:
        source.description = data.description  # type: ignore[assignment]

    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(
        select(HelmChartSource).where(HelmChartSource.id == source_id)
    )
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
    _=Depends(require_operator()),
):
    """Re-index a Helm chart source (fetch index.yaml and update versions)."""
    result = await db.execute(
        select(HelmChartSource).where(HelmChartSource.id == source_id)
    )
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


# ──── Versions ─────────────────────────────────────────────────────────────


@router.get("/{source_id}/versions", response_model=list[HelmChartVersionOut])
async def list_versions(
    source_id: int,
    chart_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
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
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(HelmSyncLog)
        .where(HelmSyncLog.source_id == source_id)
        .order_by(HelmSyncLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
