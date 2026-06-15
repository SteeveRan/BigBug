"""
@file source_group.py
@description Pydantic schemas for SourceGroup CRUD operations.
@dependencies pydantic
@relatedFiles ../models/source_group.py, ./source_provider.py, ./source_repository.py
"""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.schemas.source_repository import SourceRepositoryListOut


# ──── SourceGroup Create ───────────────────────────────────────────────────


class SourceGroupCreate(BaseModel):
    """Payload to register a new source group (org/group) for discovery."""

    name: str = Field(..., max_length=255)
    full_path: str | None = Field(None, max_length=1000)
    web_url: str | None = Field(None, max_length=500)
    description: str | None = Field(None)


class SourceGroupUpdate(BaseModel):
    """Partial update for a source group."""

    name: str | None = Field(None, max_length=255)
    full_path: str | None = Field(None, max_length=1000)
    web_url: str | None = Field(None, max_length=500)
    description: str | None = Field(None)


# ──── SourceGroup Out ──────────────────────────────────────────────────────


class SourceGroupListOut(BaseModel):
    """Flat representation for list endpoints."""

    id: int
    name: str
    full_path: str | None = None
    web_url: str | None = None
    total_repos: int
    mirrored_repos: int
    last_synced_at: datetime | None = None
    is_deleted: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceGroupDetailOut(BaseModel):
    """Detailed representation with nested relations."""

    id: int
    name: str
    full_path: str | None = None
    web_url: str | None = None
    description: str | None = None
    external_id: str | None = None
    total_repos: int
    mirrored_repos: int
    last_synced_at: datetime | None = None
    is_deleted: bool
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    source_repositories: list[SourceRepositoryListOut] = []

    model_config = {"from_attributes": True}
