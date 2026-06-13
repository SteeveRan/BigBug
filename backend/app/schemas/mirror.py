"""
@file mirror.py
@description Pydantic schemas for Mirror CRUD operations.
             Replaces old GitlabMirror schemas (already removed).
@dependencies pydantic
@relatedFiles ../models/mirror.py, ./source_repository.py, ./sync_group.py, ./mirror_log.py
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.schemas.mirror_log import MirrorLogOut
    from app.schemas.source_repository import SourceRepositoryDetailOut, SourceRepositoryListOut
    from app.schemas.sync_group import SyncGroupOut


# ──── Mirror Create ────────────────────────────────────────────────────────


class MirrorCreate(BaseModel):
    """Payload to create a single mirror."""

    source_repository_id: int
    sync_group_id: int | None = Field(None)
    target_namespace: str = Field(..., max_length=500)
    target_project_name: str = Field(..., max_length=255)


class MirrorBulkCreate(BaseModel):
    """Payload to create multiple mirrors at once, sharing defaults."""

    mirrors: list[MirrorCreate]
    default_sync_group_id: int | None = Field(None)
    default_target_namespace: str | None = Field(None, max_length=500)


class MirrorUpdate(BaseModel):
    """Partial update for a mirror — only target fields are mutable."""

    sync_group_id: int | None = Field(None)
    target_namespace: str | None = Field(None, max_length=500)
    target_project_name: str | None = Field(None, max_length=255)


# ──── Mirror Out ───────────────────────────────────────────────────────────


class MirrorListOut(BaseModel):
    """Flat representation for list endpoints."""

    id: int
    source_repository_id: int
    sync_group_id: int | None = None
    target_namespace: str | None = None
    target_project_name: str | None = None
    target_project_id: str | None = None
    target_web_url: str | None = None
    status_flag: int
    status_text: str | None = None
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_freshness_check_at: datetime | None = None
    last_freshness_status: str | None = None
    is_imported: bool
    created_at: datetime
    source_repository: SourceRepositoryListOut | None = None

    model_config = {"from_attributes": True}


class MirrorDetailOut(BaseModel):
    """Detailed representation with commit tracking and nested relations."""

    id: int
    source_repository_id: int
    sync_group_id: int | None = None
    target_namespace: str | None = None
    target_project_name: str | None = None
    target_project_id: str | None = None
    target_web_url: str | None = None
    status_flag: int
    status_text: str | None = None
    last_sync_at: datetime | None = None
    last_sync_status: str | None = None
    last_freshness_check_at: datetime | None = None
    last_freshness_status: str | None = None
    last_known_commit_sha: str | None = None
    last_known_commit_date: datetime | None = None
    last_known_commit_author: str | None = None
    target_diverged_commits: int
    is_imported: bool
    created_at: datetime
    updated_at: datetime
    source_repository: SourceRepositoryDetailOut | None = None
    sync_group: SyncGroupOut | None = None
    mirror_logs: list[MirrorLogOut] = []

    model_config = {"from_attributes": True}


# ──── Mirror Duplicate Check ───────────────────────────────────────────────


class MirrorDuplicateCheck(BaseModel):
    """Request payload for checking if a mirror with the same
    source_repository_id + target_project_name already exists."""

    source_repository_id: int
    target_project_name: str


class MirrorDuplicateCheckOut(BaseModel):
    """Response for duplicate check."""

    exists: bool
