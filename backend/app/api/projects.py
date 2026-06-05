from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.github_project import GithubProject
from app.models.github_org import GithubOrg
from app.models.github_release import GithubRelease
from app.core.rbac import require_operator, require_viewer
from app.schemas.project import (
    GithubProjectOut,
    GithubProjectListOut,
    GithubReleaseOut,
    CreateProjectRequest,
    ImportProjectRequest,
    UpdateProjectRequest,
)

router = APIRouter()


@router.get("", response_model=list[GithubProjectListOut])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(GithubProject).options(selectinload(GithubProject.org))
    )
    return result.scalars().all()


@router.get("/{project_id}", response_model=GithubProjectOut)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(GithubProject)
        .options(selectinload(GithubProject.org))
        .where(GithubProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.get("/{project_id}/releases", response_model=list[GithubReleaseOut])
async def get_project_releases(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_viewer()),
):
    result = await db.execute(
        select(GithubRelease)
        .where(GithubRelease.project_id == project_id)
        .order_by(GithubRelease.published_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=GithubProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    from app.services.github import github_service
    project = await github_service.import_project_from_url(data.github_url, db)
    return project


@router.post("/import", response_model=GithubProjectOut, status_code=status.HTTP_201_CREATED)
async def import_project(
    data: ImportProjectRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    from app.services.github import github_service
    project = await github_service.import_project_from_url(data.github_url, db)
    return project


@router.patch("/{project_id}", response_model=GithubProjectOut)
async def update_project(
    project_id: int,
    data: UpdateProjectRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(
        select(GithubProject)
        .options(selectinload(GithubProject.org))
        .where(GithubProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if data.custom_description is not None:
        project.custom_description = data.custom_description
    if data.stale_threshold_days is not None:
        project.stale_threshold_days = data.stale_threshold_days

    await db.commit()
    # Refresh only modified scalar attributes; keep eagerly-loaded relationships intact.
    await db.refresh(project, attribute_names=["custom_description", "stale_threshold_days"])
    return project


@router.post("/{project_id}/refresh", response_model=GithubProjectOut)
async def refresh_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    """Re-fetch metadata from GitHub API."""
    result = await db.execute(
        select(GithubProject)
        .options(selectinload(GithubProject.org))
        .where(GithubProject.id == project_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    from app.services.github import github_service
    await github_service.refresh_project(project, db)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_operator()),
):
    result = await db.execute(select(GithubProject).where(GithubProject.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    await db.delete(project)
    await db.commit()
