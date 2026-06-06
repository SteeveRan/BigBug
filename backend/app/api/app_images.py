from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_operator, require_viewer
from app.database import get_db
from app.models.app_image import AppImage
from app.models.build_schedule import BuildSchedule
from app.models.image_version import ImageVersion
from app.schemas.image import (
    AppImageOut,
    BuildScheduleOut,
    CreateAppImageRequest,
    CreateImageVersionRequest,
    ImageVersionOut,
    UpdateAppImageRequest,
    UpdateBuildScheduleRequest,
)

router = APIRouter()


@router.get("", response_model=list[AppImageOut])
async def list_app_images(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(select(AppImage))
    return result.scalars().all()


@router.get("/{image_id}", response_model=AppImageOut)
async def get_app_image(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(select(AppImage).where(AppImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="App image not found"
        )
    return image


@router.post("", response_model=AppImageOut, status_code=status.HTTP_201_CREATED)
async def create_app_image(
    data: CreateAppImageRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    image = AppImage(**data.model_dump())
    db.add(image)
    await db.flush()

    # Create default build schedule
    schedule = BuildSchedule(
        image_type="app",
        app_image_id=image.id,
        is_enabled=True,
        use_default_schedule=True,
    )
    db.add(schedule)

    await db.commit()
    await db.refresh(image)
    return image


@router.patch("/{image_id}", response_model=AppImageOut)
async def update_app_image(
    image_id: int,
    data: UpdateAppImageRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(select(AppImage).where(AppImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="App image not found"
        )

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(image, field, value)

    await db.commit()
    await db.refresh(image)
    return image


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app_image(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(select(AppImage).where(AppImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="App image not found"
        )
    await db.delete(image)
    await db.commit()


@router.get("/{image_id}/versions", response_model=list[ImageVersionOut])
async def list_versions(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(ImageVersion)
        .where(ImageVersion.app_image_id == image_id, ImageVersion.image_type == "app")
        .order_by(ImageVersion.created_at.desc())
    )
    return result.scalars().all()


@router.post(
    "/{image_id}/build",
    response_model=ImageVersionOut,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_build(
    image_id: int,
    data: CreateImageVersionRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(select(AppImage).where(AppImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="App image not found"
        )

    from app.services.build import build_service

    version = await build_service.trigger_app_build(
        image, data.version_tag, data.arch, db
    )
    return version


@router.get("/{image_id}/schedule", response_model=BuildScheduleOut)
async def get_build_schedule(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(BuildSchedule).where(
            BuildSchedule.app_image_id == image_id,
            BuildSchedule.image_type == "app",
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
    return schedule


@router.patch("/{image_id}/schedule", response_model=BuildScheduleOut)
async def update_build_schedule(
    image_id: int,
    data: UpdateBuildScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(
        select(BuildSchedule).where(
            BuildSchedule.app_image_id == image_id,
            BuildSchedule.image_type == "app",
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(schedule, field, value)

    await db.commit()
    await db.refresh(schedule)
    return schedule
