from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.database import get_db
from app.models.build_schedule import BuildSchedule
from app.models.gold_image import GoldImage
from app.models.image_version import ImageVersion
from app.schemas.image import (
    BuildScheduleOut,
    CreateGoldImageRequest,
    CreateImageVersionRequest,
    GoldImageOut,
    ImageVersionOut,
    SignImageRequest,
    SignImageResult,
    UpdateBuildScheduleRequest,
    UpdateGoldImageRequest,
    VerifyImageRequest,
    VerifyImageResult,
)

router = APIRouter()


@router.get("", response_model=list[GoldImageOut])
async def list_gold_images(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:read")),
):
    result = await db.execute(select(GoldImage))
    return result.scalars().all()


@router.get("/{image_id}", response_model=GoldImageOut)
async def get_gold_image(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:read")),
):
    result = await db.execute(select(GoldImage).where(GoldImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gold image not found")
    return image


@router.post("", response_model=GoldImageOut, status_code=status.HTTP_201_CREATED)
async def create_gold_image(
    data: CreateGoldImageRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:write")),
):
    image = GoldImage(**data.model_dump())
    db.add(image)
    await db.flush()

    # Create default build schedule
    schedule = BuildSchedule(
        image_type="gold",
        gold_image_id=image.id,
        is_enabled=True,
        use_default_schedule=True,
    )
    db.add(schedule)

    await db.commit()
    await db.refresh(image)
    return image


@router.patch("/{image_id}", response_model=GoldImageOut)
async def update_gold_image(
    image_id: int,
    data: UpdateGoldImageRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:write")),
):
    result = await db.execute(select(GoldImage).where(GoldImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gold image not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(image, field, value)

    await db.commit()
    await db.refresh(image)
    return image


@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gold_image(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:delete")),
):
    result = await db.execute(select(GoldImage).where(GoldImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gold image not found")
    await db.delete(image)
    await db.commit()


@router.get("/{image_id}/versions", response_model=list[ImageVersionOut])
async def list_versions(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:read")),
):
    result = await db.execute(
        select(ImageVersion)
        .where(ImageVersion.gold_image_id == image_id, ImageVersion.image_type == "gold")
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
    _=Depends(require_permission("gold_images:build")),
):
    result = await db.execute(select(GoldImage).where(GoldImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Gold image not found")

    from app.services.build import build_service

    version = await build_service.trigger_gold_build(image, data.version_tag, data.arch, db)
    return version


@router.get("/{image_id}/schedule", response_model=BuildScheduleOut)
async def get_build_schedule(
    image_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:read")),
):
    result = await db.execute(
        select(BuildSchedule).where(
            BuildSchedule.gold_image_id == image_id,
            BuildSchedule.image_type == "gold",
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return schedule


@router.patch("/{image_id}/schedule", response_model=BuildScheduleOut)
async def update_build_schedule(
    image_id: int,
    data: UpdateBuildScheduleRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:write")),
):
    result = await db.execute(
        select(BuildSchedule).where(
            BuildSchedule.gold_image_id == image_id,
            BuildSchedule.image_type == "gold",
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    for field, value in data.model_dump(exclude_none=True).items():
        setattr(schedule, field, value)

    await db.commit()
    await db.refresh(schedule)
    return schedule


# ---------------------------------------------------------------------------
# Vulnerability scanning (Harbor)
# ---------------------------------------------------------------------------


@router.post("/{image_id}/versions/{version_id}/scan")
async def scan_gold_image_version(
    image_id: int,
    version_id: int,
    harbor_instance_id: int,
    project_name: str,
    repository_name: str,
    artifact_digest: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:write")),
):
    """Trigger Harbor vulnerability scan for a gold image version."""
    from app.services.harbor_scan import HarborScanService

    return await HarborScanService.scan_image(
        db,
        image_version_id=version_id,
        harbor_instance_id=harbor_instance_id,
        project_name=project_name,
        repository_name=repository_name,
        artifact_digest=artifact_digest,
    )


@router.post("/{image_id}/versions/{version_id}/scan/results")
async def get_gold_image_scan_results(
    image_id: int,
    version_id: int,
    harbor_instance_id: int,
    project_name: str,
    repository_name: str,
    artifact_digest: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:read")),
):
    """Get Harbor vulnerability scan results for a gold image version."""
    from app.services.harbor_scan import HarborScanService

    return await HarborScanService.get_scan_results(
        db,
        image_version_id=version_id,
        harbor_instance_id=harbor_instance_id,
        project_name=project_name,
        repository_name=repository_name,
        artifact_digest=artifact_digest,
    )


# ---------------------------------------------------------------------------
# Cosign image signing
# ---------------------------------------------------------------------------


@router.post("/{image_id}/versions/{version_id}/sign", response_model=SignImageResult)
async def sign_gold_image_version(
    image_id: int,
    version_id: int,
    data: SignImageRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:write")),
):
    """Sign a gold image version using cosign."""
    from app.services.cosign import CosignService

    return await CosignService.sign_image(
        db,
        image_version_id=version_id,
        image_reference=data.image_reference,
        cosign_private_key=data.cosign_private_key,
    )


@router.post("/{image_id}/versions/{version_id}/verify", response_model=VerifyImageResult)
async def verify_gold_image_version(
    image_id: int,
    version_id: int,
    data: VerifyImageRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("gold_images:read")),
):
    """Verify cosign signature for a gold image version."""
    from app.services.cosign import CosignService

    return await CosignService.verify_image(
        db,
        image_version_id=version_id,
        image_reference=data.image_reference,
        cosign_public_key=data.cosign_public_key,
    )
