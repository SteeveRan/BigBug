from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.rbac import require_permission
from app.database import get_db
from app.models.docker_image_source import DockerImageSource
from app.models.docker_image_tag import DockerImageTag
from app.models.docker_sync_log import DockerSyncLog
from app.models.sync_schedule import SyncSchedule
from app.schemas.docker import (
    BatchDeleteTagsRequest,
    CreateDockerImageSourceRequest,
    CreateDockerSyncScheduleRequest,
    DockerImageCompareResponse,
    DockerImageSourceDetailOut,
    DockerImageSourceOut,
    DockerImageTagCompareItem,
    DockerImageTagOut,
    DockerSyncLogOut,
    DockerSyncScheduleOut,
    UpdateDockerImageSourceRequest,
    UpdateDockerSyncScheduleRequest,
)
from app.schemas.provider import ProviderOut

router = APIRouter()


# ──── Sources CRUD ─────────────────────────────────────────────────────────


@router.get("", response_model=list[DockerImageSourceOut])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:read")),
):
    result = await db.execute(
        select(DockerImageSource).options(
            selectinload(DockerImageSource.provider),
            selectinload(DockerImageSource.target_provider),
        )
    )
    return result.scalars().all()


@router.get("/{source_id}", response_model=DockerImageSourceDetailOut)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:read")),
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


@router.post("", response_model=DockerImageSourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    data: CreateDockerImageSourceRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:write")),
):
    from app.services.docker import docker_service

    source = await docker_service.import_source_from_url(
        data.name,
        data.registry_url,
        data.image_name,
        db,
        target_registry_url=data.target_registry_url,
        target_project=data.target_project,
        provider_id=data.provider_id,
        target_provider_id=data.target_provider_id,
    )
    return source


@router.patch("/{source_id}", response_model=DockerImageSourceOut)
async def update_source(
    source_id: int,
    data: UpdateDockerImageSourceRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:write")),
):
    result = await db.execute(select(DockerImageSource).where(DockerImageSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docker image source not found",
        )

    if data.provider_id is not None or data.target_provider_id is not None:
        # Providers V3 (11.3.4): validate links before assigning.
        from app.services.docker import (
            _get_docker_provider_or_404,
        )

        if data.provider_id is not None:
            await _get_docker_provider_or_404(db, data.provider_id)
            source.provider_id = data.provider_id  # type: ignore[assignment]
        if data.target_provider_id is not None:
            await _get_docker_provider_or_404(db, data.target_provider_id, internal_only=True)
            source.target_provider_id = data.target_provider_id  # type: ignore[assignment]

    if data.name is not None:
        source.name = data.name  # type: ignore[assignment]
    if data.registry_url is not None:
        source.registry_url = data.registry_url  # type: ignore[assignment]
    if data.description is not None:
        source.description = data.description  # type: ignore[assignment]
    if data.target_registry_url is not None:
        source.target_registry_url = data.target_registry_url  # type: ignore[assignment]
    if data.target_project is not None:
        source.target_project = data.target_project  # type: ignore[assignment]

    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:delete")),
):
    result = await db.execute(select(DockerImageSource).where(DockerImageSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docker image source not found",
        )
    await db.delete(source)
    await db.commit()


# ──── Compare ──────────────────────────────────────────────────────────────


@router.get("/{source_id}/compare/{other_source_id}", response_model=DockerImageCompareResponse)
async def compare_docker_sources(
    source_id: int,
    other_source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:read")),
) -> dict:
    """
    Compare tags between two Docker image sources.

    Compares tags by name and shows which tags are:
    - Matching (same digest in both sources)
    - Differing (different digests)
    - Only in one source
    """
    # Load both sources
    source_a = await db.get(DockerImageSource, source_id)
    if not source_a:
        raise HTTPException(status_code=404, detail="Source A not found")

    source_b = await db.get(DockerImageSource, other_source_id)
    if not source_b:
        raise HTTPException(status_code=404, detail="Source B not found")

    # Load tags for both sources
    tags_a_result = await db.execute(
        select(DockerImageTag).where(DockerImageTag.source_id == source_id)
    )
    tags_a = tags_a_result.scalars().all()

    tags_b_result = await db.execute(
        select(DockerImageTag).where(DockerImageTag.source_id == other_source_id)
    )
    tags_b = tags_b_result.scalars().all()

    # Build maps by tag name
    map_a = {t.tag: t for t in tags_a}
    map_b = {t.tag: t for t in tags_b}

    all_tag_names = set(map_a.keys()) | set(map_b.keys())

    # Build comparison items
    tags = []
    matching = differing = only_a = only_b = 0

    for tag_name in sorted(all_tag_names):
        t_a = map_a.get(tag_name)
        t_b = map_b.get(tag_name)

        item = DockerImageTagCompareItem(
            tag=tag_name,
            digest_a=t_a.digest if t_a else None,
            digest_b=t_b.digest if t_b else None,
            architectures_a=t_a.architectures if t_a else None,
            architectures_b=t_b.architectures if t_b else None,
            size_bytes_a=t_a.size_bytes if t_a else None,
            size_bytes_b=t_b.size_bytes if t_b else None,
        )

        if t_a and t_b:
            item.match = t_a.digest == t_b.digest
            if item.match:
                matching += 1
            else:
                differing += 1
        elif t_a:
            only_a += 1
        else:
            only_b += 1

        tags.append(item)

    return {
        "source_a": source_a,
        "source_b": source_b,
        "tags": tags,
        "summary": {
            "total_tags": len(all_tag_names),
            "matching_tags": matching,
            "differing_tags": differing,
            "only_in_a": only_a,
            "only_in_b": only_b,
        },
    }


# ──── Index / Sync ─────────────────────────────────────────────────────────


@router.post("/{source_id}/index", response_model=DockerSyncLogOut)
async def index_source(
    source_id: int,
    image_name: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:index")),
):
    """Re-index tags for a Docker image source (fetch from registry and update tags)."""
    result = await db.execute(select(DockerImageSource).where(DockerImageSource.id == source_id))
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


# ──── Mirror ────────────────────────────────────────────────────────────────


@router.post("/{source_id}/mirror", response_model=DockerSyncLogOut)
async def mirror_image(
    source_id: int,
    image_name: str = Query(..., description="Image name to mirror"),
    tag: str = Query("latest", description="Image tag to mirror"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_permission("docker:sync")),
) -> DockerSyncLog:
    """Mirror a Docker image from the external source to the target registry."""
    source = await db.get(DockerImageSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Docker image source not found")

    if not source.target_registry_url:
        raise HTTPException(
            status_code=400,
            detail="Source has no target registry configured. Set target_registry_url first.",
        )

    from app.services.docker import docker_service

    try:
        log = await docker_service.mirror_image(
            source=source,
            image_name=image_name,
            tag=tag,
            db=db,
            triggered_by=f"user:{current_user.username}",
        )
        return log
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ──── Tags ─────────────────────────────────────────────────────────────────


@router.get("/{source_id}/tags", response_model=list[DockerImageTagOut])
async def list_tags(
    source_id: int,
    image_name: str | None = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:read")),
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
    _=Depends(require_permission("docker:read")),
):
    result = await db.execute(
        select(DockerSyncLog)
        .where(DockerSyncLog.source_id == source_id)
        .order_by(DockerSyncLog.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


# ──── Batch Delete Tags ────────────────────────────────────────────────────


@router.delete("/{source_id}/tags/batch", status_code=status.HTTP_204_NO_CONTENT)
async def batch_delete_tags(
    source_id: int,
    data: BatchDeleteTagsRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:delete")),
) -> None:
    """
    Delete multiple Docker image tags for a source.

    Deletes all specified tags in a single transaction.
    Returns 204 No Content on success.
    Returns 404 if the source doesn't exist.
    """
    # 1. Verify source exists
    source = await db.get(DockerImageSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docker image source not found",
        )

    # 2. Find all tags matching the provided ids and belonging to this source
    result = await db.execute(
        select(DockerImageTag).where(
            DockerImageTag.source_id == source_id,
            DockerImageTag.id.in_(data.tag_ids),
        )
    )
    tags = result.scalars().all()

    # 3. Delete found tags
    for tag in tags:
        await db.delete(tag)

    # 4. Commit — idempotent: if no tags found, still returns 204
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ──── Sync Schedule ─────────────────────────────────────────────────────────


@router.get("/{source_id}/schedule", response_model=list[DockerSyncScheduleOut])
async def get_docker_sync_schedules(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:read")),
):
    """Get all sync schedules for a Docker image source."""
    source = await db.get(DockerImageSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docker image source not found",
        )

    result = await db.execute(
        select(SyncSchedule).where(
            SyncSchedule.sync_type == "docker_image",
            SyncSchedule.docker_image_source_id == source_id,
        )
    )
    return result.scalars().all()


@router.post(
    "/{source_id}/schedule",
    response_model=DockerSyncScheduleOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_docker_sync_schedule(
    source_id: int,
    data: CreateDockerSyncScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:write")),
):
    """Create a sync schedule for a Docker image source."""
    source = await db.get(DockerImageSource, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Docker image source not found",
        )

    schedule = SyncSchedule(
        sync_type="docker_image",
        docker_image_source_id=source_id,
        cron_expression=data.cron_expression,
        is_enabled=data.is_enabled,
        use_default_schedule=data.use_default_schedule,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.patch("/{source_id}/schedule/{schedule_id}", response_model=DockerSyncScheduleOut)
async def update_docker_sync_schedule(
    source_id: int,
    schedule_id: int,
    data: UpdateDockerSyncScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:write")),
):
    """Update a sync schedule."""
    result = await db.execute(
        select(SyncSchedule).where(
            SyncSchedule.id == schedule_id,
            SyncSchedule.sync_type == "docker_image",
            SyncSchedule.docker_image_source_id == source_id,
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
async def delete_docker_sync_schedule(
    source_id: int,
    schedule_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:delete")),
):
    """Delete a sync schedule."""
    result = await db.execute(
        select(SyncSchedule).where(
            SyncSchedule.id == schedule_id,
            SyncSchedule.sync_type == "docker_image",
            SyncSchedule.docker_image_source_id == source_id,
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


# ──── Image Analysis ────────────────────────────────────────────────────────


class AnalyzeImageRequest(BaseModel):
    """Request to analyze an image reference and suggest matching registries."""

    image_name: str = Field(
        ..., min_length=1, max_length=500, description="Image reference (e.g. nginx:latest)"
    )


class AnalyzeImageResponse(BaseModel):
    """Result of image analysis with registry matching suggestions."""

    image_name: str
    normalized_image: str
    detected_registry_host: str
    detected_provider: str
    suggested_registry: ProviderOut | None = None
    compatible_registries: list[ProviderOut] = []
    is_new_registry_needed: bool = False
    available_targets: list[ProviderOut] = []
    repository_path: str  # clean repo path without host/tag


@router.post("/analyze", response_model=AnalyzeImageResponse)
async def analyze_image(
    data: AnalyzeImageRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("docker:read")),
):
    """
    Analyze an image reference and suggest matching registry instances.

    Returns the detected registry host, provider, and a list of compatible
    configured registry instances that can serve as the source.
    """
    from app.services.docker import (
        find_matching_docker_provider,
        get_compatible_docker_providers,
        get_internal_docker_targets,
        normalize_registry_image_ref,
        parse_registry_from_image,
        repository_path_from_ref,
    )

    image_name = data.image_name.strip()
    registry_host, provider = parse_registry_from_image(image_name)
    normalized = normalize_registry_image_ref(image_name)

    suggested = await find_matching_docker_provider(db, registry_host, provider)
    compatible = await get_compatible_docker_providers(db, registry_host, provider)
    targets = await get_internal_docker_targets(db)

    return AnalyzeImageResponse(
        image_name=image_name,
        normalized_image=normalized,
        detected_registry_host=registry_host,
        detected_provider=provider,
        suggested_registry=ProviderOut.model_validate(suggested) if suggested else None,
        compatible_registries=[ProviderOut.model_validate(r) for r in compatible],
        is_new_registry_needed=suggested is None,
        available_targets=[ProviderOut.model_validate(r) for r in targets],
        repository_path=repository_path_from_ref(image_name),
    )
