"""
@file orphaned.py
@description REST API for discovering orphaned mirrors — GitLab projects
             not tracked by any BigBug mirror record.
@dependencies FastAPI, app.services.orphaned
@relatedFiles ../services/orphaned.py, ../schemas/mirror.py
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError, NotFoundError
from app.core.rbac import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.mirror import OrphanedMirrorOut
from app.services.orphaned import OrphanedMirrorService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/orphaned-mirrors",
    response_model=list[OrphanedMirrorOut],
)
async def list_orphaned_mirrors(
    gitlab_instance_id: int | None = Query(
        None,
        description="Limit scan to a specific GitLab instance. "
        "If omitted, scans all configured instances.",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrphanedMirrorOut]:
    """List GitLab projects not tracked by any BigBug Mirror.

    Scans the GitLab API for projects and compares them against
    known BigBug mirrors.  Projects without a matching mirror
    record are reported as orphaned.
    """
    try:
        report = await OrphanedMirrorService.find_orphaned(
            db,
            gitlab_instance_id=gitlab_instance_id,
        )
    except (DomainError, NotFoundError) as e:
        status_code = e.status_code if isinstance(e, DomainError) else 404
        raise HTTPException(status_code=status_code, detail=str(e)) from e

    return [
        OrphanedMirrorOut(
            mirror_id=item.gitlab_project_id,
            target_path=item.target_path,
            target_web_url=item.target_web_url,
            reason=item.reason,
            created_at=item.created_at,
            source_repository_name=item.source_repository_name,
        )
        for item in report.items
    ]
