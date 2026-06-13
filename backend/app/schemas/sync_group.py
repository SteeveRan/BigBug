"""
@file sync_group.py
@description Pydantic schemas for SyncGroup CRUD operations.
@dependencies pydantic
@relatedFiles ../models/sync_group.py, ./pipeline.py
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, computed_field

if TYPE_CHECKING:
    from app.schemas.pipeline import PipelineOut


# ──── SyncGroup Create ─────────────────────────────────────────────────────


class SyncGroupCreate(BaseModel):
    """Payload to create a new sync group."""

    name: str = Field(..., max_length=255, description="Unique name")
    description: str | None = Field(None)
    pipeline_id: int | None = Field(None)
    sync_cron: str | None = Field(None, max_length=100)
    sync_enabled: bool = Field(True)
    sync_concurrency: int = Field(1, ge=1)
    freshness_cron: str | None = Field(None, max_length=100)
    freshness_enabled: bool = Field(False)
    freshness_concurrency: int = Field(1, ge=1)


class SyncGroupUpdate(BaseModel):
    """Partial update for a sync group."""

    description: str | None = Field(None)
    pipeline_id: int | None = Field(None)
    sync_cron: str | None = Field(None, max_length=100)
    sync_enabled: bool | None = Field(None)
    sync_concurrency: int | None = Field(None, ge=1)
    freshness_cron: str | None = Field(None, max_length=100)
    freshness_enabled: bool | None = Field(None)
    freshness_concurrency: int | None = Field(None, ge=1)
    is_deleted: bool | None = Field(None)


# ──── SyncGroup Out ────────────────────────────────────────────────────────


class SyncGroupOut(BaseModel):
    """Public representation of a sync group."""

    id: int
    name: str
    description: str | None = None
    pipeline_id: int | None = None
    is_default: bool
    sync_cron: str | None = None
    sync_enabled: bool
    sync_concurrency: int
    freshness_cron: str | None = None
    freshness_enabled: bool
    freshness_concurrency: int
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    pipeline: PipelineOut | None = None

    @computed_field
    def mirrors_count(self) -> int:
        """Computed count of mirrors in this sync group."""
        # The model may have mirrors loaded; use len if available, else 0
        if hasattr(self, "_mirrors"):
            return len(self._mirrors)
        return 0

    model_config = {"from_attributes": True}
