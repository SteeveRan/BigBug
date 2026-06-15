"""
@file source_repository.py
@description Pydantic schemas for SourceRepository CRUD operations.
@dependencies pydantic
@relatedFiles ../models/source_repository.py, ./source_group.py, ./mirror.py
"""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.models.source_provider import ProviderType

if TYPE_CHECKING:
    from app.schemas.mirror import MirrorListOut
    from app.schemas.source_group import SourceGroupListOut
    from app.schemas.source_provider import SourceProviderOut


# ──── SourceRepository List Out ────────────────────────────────────────────


class SourceRepositoryListOut(BaseModel):
    """Flat representation for list endpoints."""

    id: int
    source_provider_id: int | None = None
    source_group_id: int | None
    name: str
    full_name: str
    web_url: str | None = None
    description: str | None = None
    language: str | None = None
    stars_count: int = 0
    forks_count: int = 0
    is_private: bool = False
    default_branch: str | None = None
    is_archived: bool
    is_fork: bool
    discovery_status: str
    latest_release_tag: str | None = None
    latest_release_date: datetime | None = None
    latest_prerelease_tag: str | None = None
    latest_prerelease_date: datetime | None = None
    source_pushed_at: datetime | None = None
    last_seen_at: datetime | None = None
    is_deleted: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceRepositoryDetailOut(BaseModel):
    """Full representation with all fields and nested relations."""

    id: int
    source_provider_id: int | None = None
    source_group_id: int | None
    name: str
    full_name: str
    web_url: str | None = None
    clone_url_https: str | None = None
    clone_url_ssh: str | None = None
    description: str | None = None
    language: str | None = None
    stars_count: int = 0
    forks_count: int = 0
    is_private: bool = False
    default_branch: str | None = None
    license_spdx: str | None = None
    license_name: str | None = None
    readme_html: str | None = None
    readme_fetched_at: datetime | None = None
    latest_release_tag: str | None = None
    latest_release_name: str | None = None
    latest_release_date: datetime | None = None
    latest_release_url: str | None = None
    latest_prerelease_tag: str | None = None
    latest_prerelease_name: str | None = None
    latest_prerelease_date: datetime | None = None
    latest_prerelease_url: str | None = None
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
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    source_provider: SourceProviderOut | None = None
    source_group: SourceGroupListOut | None = None
    mirrors: list[MirrorListOut] = []

    model_config = {"from_attributes": True}


# ──── SourceRepository Create ──────────────────────────────────────────────


class SourceRepositoryCreate(BaseModel):
    """Schema for creating a source repository manually.

    ``source_group_id`` is resolved automatically:
    - For **github** / **gitlab** the first segment of the clone URL path
      (e.g. ``org`` from ``org/repo``) is used to find or auto-create a
      SourceGroup.
    - For **generic** it is always ``None``.
    """

    provider_type: ProviderType
    clone_url: str = Field(..., description="HTTPS or SSH clone URL")
    source_provider_id: int | None = Field(None, description="Provider ID (null for generic git)")


# ──── SourceRepository Readme / Release ────────────────────────────────────


class SourceRepositoryReadmeOut(BaseModel):
    """Cached README content for a source repository."""

    readme_html: str | None = None
    readme_fetched_at: datetime | None = None

    model_config = {"from_attributes": True}


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
