from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.docker_image_source import DockerImageSource
from app.models.docker_image_tag import DockerImageTag
from app.models.docker_sync_log import DockerSyncLog
from app.core.rbac import require_operator, require_viewer
from app.schemas.docker import (
    DockerImageSourceOut,
    DockerImageSourceDetailOut,
    DockerImageTagOut,
    DockerSyncLogOut,
    CreateDockerImageSourceRequest,
    UpdateDockerImageSourceRequest,
)

router = APIRouter()


# ──── Sources CRUD ─────────────────────────────────────────────────────────

@router.get("", response_model=list[DockerImageSourceOut])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(select(DockerImageSource))
    return result.scalars().all()


@router.get("/{source_id}", response_model=DockerImageSourceDetailOut)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(DockerImageSource)
        .options(selectinload(DockerImageSource.tags))
        .where(DockerImageSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docker image source not found",
        )
    return source


@router.post(
    "", response_model=DockerImageSourceOut, status_code=status.HTTP_201_CREATED
)
async def create_source(
    data: CreateDockerImageSourceRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    from app.services.docker import docker_service

    source = await docker_service.import_source_from_url(
        data.name, data.registry_url, data.image_name, db
    )
    return source


@router.patch("/{source_id}", response_model=DockerImageSourceOut)
async def update_source(
    source_id: int,
    data: UpdateDockerImageSourceRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(
        select(DockerImageSource).where(DockerImageSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docker image source not found",
        )

    if data.name is not None:
        source.name = data.name  # type: ignore[assignment]
    if data.registry_url is not None:
        source.registry_url = data.registry_url  # type: ignore[assignment]
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
        select(DockerImageSource).where(DockerImageSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docker image source not found",
        )
    await db.delete(source)
    await db.commit()


# ──── Index / Sync ─────────────────────────────────────────────────────────

@router.post("/{source_id}/index", response_model=DockerSyncLogOut)
async def index_source(
    source_id: int,
    image_name: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    """Re-index tags for a Docker image source (fetch from registry and update tags)."""
    result = await db.execute(
        select(DockerImageSource).where(DockerImageSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docker image source not found",
        )

    from app.services.docker import docker_service

    sync_log = await docker_service.refresh_source(source, image_name, db)
    await db.commit()
    await db.refresh(sync_log)
    return sync_log


# ──── Tags ─────────────────────────────────────────────────────────────────

@router.get("/{source_id}/tags", response_model=list[DockerImageTagOut])
async def list_tags(
    source_id: int,
    image_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    """List image tags for a source. Optionally filter by image_name."""
    stmt = (
        select(DockerImageTag)
        .where(DockerImageTag.source_id == source_id)
        .order_by(
            DockerImageTag.image_name,
            DockerImageTag.tag.desc(),
        )
    )
    if image_name:
        stmt = stmt.where(DockerImageTag.image_name == image_name)

    result = await db.execute(stmt)
    return result.scalars().all()


# ──── Sync Logs ────────────────────────────────────────────────────────────

@router.get("/{source_id}/logs", response_model=list[DockerSyncLogOut])
async def get_sync_logs(
    source_id: int,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(DockerSyncLog)
        .where(DockerSyncLog.source_id == source_id)
        .order_by(DockerSyncLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
