"""
@file source_repository.py
@description Pydantic schemas for SourceRepository CRUD operations.
@dependencies pydantic
@relatedFiles ../models/source_repository.py, ./source_group.py, ./mirror.py
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.schemas.mirror import MirrorListOut
    from app.schemas.source_group import SourceGroupListOut


# ──── SourceRepository List Out ────────────────────────────────────────────


class SourceRepositoryListOut(BaseModel):
    """Flat representation for list endpoints."""

    id: int
    source_group_id: int
    name: str
    full_name: str
    web_url: str | None = None
    default_branch: str | None = None
    is_archived: bool
    is_fork: bool
    discovery_status: str
    latest_release_tag: str | None = None
    latest_release_date: datetime | None = None
    source_pushed_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceRepositoryDetailOut(BaseModel):
    """Full representation with all fields and nested relations."""

    id: int
    source_group_id: int
    name: str
    full_name: str
    web_url: str | None = None
    clone_url_https: str | None = None
    clone_url_ssh: str | None = None
    description: str | None = None
    default_branch: str | None = None
    license_spdx: str | None = None
    license_name: str | None = None
    readme_html: str | None = None
    readme_fetched_at: datetime | None = None
    latest_release_tag: str | None = None
    latest_release_date: datetime | None = None
    is_archived: bool
    is_fork: bool
    is_disabled: bool
    discovery_status: str
    discovered_at: datetime | None = None
    last_seen_at: datetime | None = None
    source_created_at: datetime | None = None
    source_updated_at: datetime | None = None
    source_pushed_at: datetime | None = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
    source_group: SourceGroupListOut | None = None
    mirrors: list[MirrorListOut] = []

    model_config = {"from_attributes": True}


# ──── SourceRepository Readme / Release ────────────────────────────────────


class SourceRepositoryReleaseOut(BaseModel):
    """Release information for a source repository."""

    tag: str | None = None
    name: str | None = None
    description: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    is_prerelease: bool = False
    detected_at: datetime | None = None

    model_config = {"from_attributes": True}


class SourceRepositoryReadmeOut(BaseModel):
    """README content for a source repository."""

    readme_html: str | None = None
    readme_fetched_at: datetime | None = None

    model_config = {"from_attributes": True}
