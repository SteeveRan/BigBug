"""
@file gitlab_projects.py
@description REST API for GitLab project management — CRUD, import, sync, files,
              tags and team sharing. Maps :class:`app.core.exceptions.DomainError`
              raised by :class:`app.services.gitlab_projects.GitlabProjectService`
              to HTTP status codes (transport stays out of the service layer).
@dependencies app.core.rbac, app.schemas.gitlab_project, app.services.gitlab_projects
@relatedFiles ../models/gitlab_project.py, ../schemas/gitlab_project.py,
              ../services/gitlab_projects/
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.core.rbac import get_current_user, require_permission
from app.database import get_db
from app.models.gitlab_project import GitlabProjectType
from app.models.user import User
from app.schemas.gitlab_project import (
    GitlabProjectCreate,
    GitlabProjectFileIn,
    GitlabProjectFileOut,
    GitlabProjectImport,
    GitlabProjectOut,
    GitlabProjectShareIn,
    GitlabProjectSyncResult,
    GitlabProjectTagIn,
    GitlabProjectTagOut,
    GitlabProjectUpdate,
)
from app.services.audit import AuditService
from app.services.gitlab_projects import GitlabProjectService

router = APIRouter()


def _translate(exc: DomainError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ──── List / detail ──────────────────────────────────────────────────────


@router.get("", response_model=list[GitlabProjectOut])
async def list_gitlab_projects(
    project_type: GitlabProjectType | None = None,
    provider_id: int | None = None,
    owner: str | None = Query(None, description="`me` to filter to caller's projects"),
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("gitlab_projects:read")),
):
    service = GitlabProjectService(db)
    projects = await service.list_projects(current_user)

    result = []
    for project in projects:
        if project_type is not None and project.project_type != project_type:
            continue
        if provider_id is not None and project.provider_id != provider_id:
            continue
        if owner == "me" and project.owner_user_id != current_user.id:
            continue
        if search and search.lower() not in project.name.lower():
            continue
        result.append(project)

    return [GitlabProjectOut.model_validate(p) for p in result]


@router.get("/{project_id}", response_model=GitlabProjectOut)
async def get_gitlab_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("gitlab_projects:read")),
):
    service = GitlabProjectService(db)
    try:
        project = await service.get_project(project_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc
    return GitlabProjectOut.model_validate(project)


# ──── Create / update / delete ──────────────────────────────────────────


@router.post("", response_model=GitlabProjectOut, status_code=status.HTTP_201_CREATED)
async def create_gitlab_project(
    data: GitlabProjectCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GitlabProjectService(db)
    try:
        project = await service.create_project(current_user, data)
    except DomainError as exc:
        raise _translate(exc) from exc

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="gitlab_project.created",
        resource_type="gitlab_project",
        resource_id=project.id,
        resource_name=project.name,
        ip_address=_client_ip(request),
    )
    return GitlabProjectOut.model_validate(project)


@router.patch("/{project_id}", response_model=GitlabProjectOut)
async def update_gitlab_project(
    project_id: int,
    data: GitlabProjectUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GitlabProjectService(db)
    try:
        project = await service.update_project(project_id, current_user, data)
    except DomainError as exc:
        raise _translate(exc) from exc

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="gitlab_project.updated",
        resource_type="gitlab_project",
        resource_id=project.id,
        resource_name=project.name,
        ip_address=_client_ip(request),
    )
    return GitlabProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gitlab_project(
    project_id: int,
    hard: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GitlabProjectService(db)
    try:
        await service.delete_project(project_id, current_user, hard)
    except DomainError as exc:
        raise _translate(exc) from exc


# ──── Import / sync ─────────────────────────────────────────────────────


@router.post("/import", response_model=GitlabProjectOut, status_code=status.HTTP_201_CREATED)
async def import_gitlab_project(
    data: GitlabProjectImport,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GitlabProjectService(db)
    try:
        project = await service.import_project(
            current_user,
            provider_id=data.provider_id,
            full_path=data.full_path,
            project_type=data.project_type,
            visibility=data.visibility,
            team_id=data.team_id,
        )
    except DomainError as exc:
        raise _translate(exc) from exc

    await AuditService.log_event(
        db,
        user_id=current_user.id,
        username=current_user.username,
        action="gitlab_project.imported",
        resource_type="gitlab_project",
        resource_id=project.id,
        resource_name=project.name,
        ip_address=_client_ip(request),
    )
    return GitlabProjectOut.model_validate(project)


@router.post("/{project_id}/sync", response_model=GitlabProjectSyncResult)
async def sync_gitlab_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("gitlab_projects:write")),
):
    service = GitlabProjectService(db)
    try:
        project = await service.sync_project(project_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc
    return GitlabProjectSyncResult(
        id=project.id,
        status_flag=project.status_flag,
        status_text=project.status_text,
        external_id=project.external_id,
        web_url=project.web_url,
        default_branch=project.default_branch,
        gitlab_visibility=project.gitlab_visibility,
        last_synced_at=project.last_synced_at,
    )


# ──── Files ─────────────────────────────────────────────────────────────


@router.get("/{project_id}/files", response_model=list[GitlabProjectFileOut])
async def list_gitlab_project_files(
    project_id: int,
    ref: str = Query("main"),
    path: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("gitlab_projects:read")),
):
    service = GitlabProjectService(db)
    try:
        items = await service.list_files(project_id, current_user, ref, path)
    except DomainError as exc:
        raise _translate(exc) from exc
    return [GitlabProjectFileOut(**item) for item in items]


@router.post("/{project_id}/files", response_model=GitlabProjectFileOut)
async def upsert_gitlab_project_file(
    project_id: int,
    data: GitlabProjectFileIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GitlabProjectService(db)
    try:
        result = await service.upsert_file(
            project_id,
            current_user,
            data.file_path,
            data.content,
            data.branch,
            data.commit_message,
            data.encoding,
        )
    except DomainError as exc:
        raise _translate(exc) from exc
    return GitlabProjectFileOut(path=result["file_path"], type="blob", content=data.content)


@router.delete("/{project_id}/files", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gitlab_project_file(
    project_id: int,
    file_path: str = Query(..., description="Repository file path"),
    branch: str | None = Query(None),
    commit_message: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GitlabProjectService(db)
    try:
        await service.delete_file(project_id, current_user, file_path, branch, commit_message)
    except DomainError as exc:
        raise _translate(exc) from exc


# ──── Tags ──────────────────────────────────────────────────────────────


@router.get("/{project_id}/tags", response_model=list[GitlabProjectTagOut])
async def list_gitlab_project_tags(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("gitlab_projects:read")),
):
    service = GitlabProjectService(db)
    try:
        items = await service.list_tags(project_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc
    return [GitlabProjectTagOut(**item) for item in items]


@router.post("/{project_id}/tags", response_model=GitlabProjectTagOut, status_code=201)
async def create_gitlab_project_tag(
    project_id: int,
    data: GitlabProjectTagIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GitlabProjectService(db)
    try:
        tag = await service.create_tag(
            project_id, current_user, data.tag_name, data.ref, data.message
        )
    except DomainError as exc:
        raise _translate(exc) from exc
    return GitlabProjectTagOut(**tag)


# ──── Share / unshare ───────────────────────────────────────────────────


@router.post("/{project_id}/share", response_model=GitlabProjectOut)
async def share_gitlab_project(
    project_id: int,
    data: GitlabProjectShareIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GitlabProjectService(db)
    try:
        project = await service.share_project(project_id, data.team_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc
    return GitlabProjectOut.model_validate(project)


@router.post("/{project_id}/unshare", response_model=GitlabProjectOut)
async def unshare_gitlab_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = GitlabProjectService(db)
    try:
        project = await service.unshare_project(project_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc
    return GitlabProjectOut.model_validate(project)
