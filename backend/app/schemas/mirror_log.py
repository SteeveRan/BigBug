"""
@file mirror_log.py
@description Pydantic schemas for MirrorLog CRUD operations.
@dependencies pydantic, app.models.mirror_log.MirrorLogType
@relatedFiles ../models/mirror_log.py, ./mirror.py, ./pipeline.py
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from app.models.mirror_log import MirrorLogType

if TYPE_CHECKING:
    from app.schemas.mirror import MirrorListOut
    from app.schemas.pipeline import PipelineRunOut


# ──── MirrorLog Create ─────────────────────────────────────────────────────


class MirrorLogCreate(BaseModel):
    """Payload to create a new mirror log entry."""

    mirror_id: int
    log_type: MirrorLogType
    pipeline_run_id: int | None = Field(None)
    status_flag: int = Field(3, description="0=OK, 1=Failed, 2=Warning, 3=In Progress, 4=Pending")
    status_text: str | None = Field(None, max_length=500)
    triggered_by: str | None = Field(None, description="scheduler, manual, webhook")


# ──── MirrorLog Out ────────────────────────────────────────────────────────


class MirrorLogOut(BaseModel):
    """Public representation of a mirror log entry."""

    id: int
    mirror_id: int
    log_type: MirrorLogType
    pipeline_run_id: int | None = None
    gitlab_pipeline_id: str | None = None
    gitlab_pipeline_url: str | None = None
    status_flag: int
    status_text: str | None = None
    source_commit_sha: str | None = None
    source_commit_date: datetime | None = None
    target_commit_sha: str | None = None
    commits_behind: int | None = None
    target_extra_commits: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    triggered_by: str | None = None
    details: dict[str, Any] | None = None
    created_at: datetime
    mirror: MirrorListOut | None = None
    pipeline_run: PipelineRunOut | None = None

    model_config = {"from_attributes": True}
