from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.provider import ProviderOut

# ──── DockerImageTag────────────────────────────────────────────────────────


class DockerImageTagOut(BaseModel):
    id: int
    source_id: int
    image_name: str
    tag: str
    digest: str | None
    size_bytes: int | None
    architectures: str | None
    is_synced: bool
    status_flag: int
    status_text: str | None
    last_synced_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ──── DockerSyncLog ────────────────────────────────────────────────────────


class DockerSyncLogOut(BaseModel):
    id: int
    source_id: int
    pipeline_id: str | None
    pipeline_url: str | None
    status_flag: int
    status_text: str | None
    log_output: str | None
    triggered_by: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ──── DockerImageSource ────────────────────────────────────────────────────


class DockerImageSourceOut(BaseModel):
    id: int
    name: str
    registry_url: str
    description: str | None
    provider_id: int | None = None
    target_provider_id: int | None = None
    provider: ProviderOut | None = None
    target_provider: ProviderOut | None = None
    gitlab_project_id: str | None
    gitlab_project_url: str | None
    target_registry_url: str | None = None
    target_project: str | None = None
    last_synced_at: datetime | None
    status_flag: int
    status_text: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DockerImageSourceDetailOut(DockerImageSourceOut):
    tags: list[DockerImageTagOut] = []

    model_config = {"from_attributes": True}


# ──── Requests ─────────────────────────────────────────────────────────────


class CreateDockerImageSourceRequest(BaseModel):
    name: str
    registry_url: str
    description: str | None = None
    image_name: str | None = None  # Optional: pre-filter to a specific image
    provider_id: int | None = None  # External docker provider (V3)
    target_provider_id: int | None = None  # Internal harbor/generic_registry provider (V3)
    target_registry_url: str | None = None
    target_project: str | None = None


class UpdateDockerImageSourceRequest(BaseModel):
    name: str | None = None
    registry_url: str | None = None
    description: str | None = None
    provider_id: int | None = None
    target_provider_id: int | None = None
    target_registry_url: str | None = None
    target_project: str | None = None


# ──── Batch Delete ─────────────────────────────────────────────────────────


class BatchDeleteTagsRequest(BaseModel):
    """Schema for batch deleting Docker image tags."""

    tag_ids: list[int] = Field(..., min_length=1, max_length=100)


# ──── Sync Schedule ─────────────────────────────────────────────────────────


class CreateDockerSyncScheduleRequest(BaseModel):
    """Schema for creating a sync schedule for a Docker image source."""

    cron_expression: str | None = None
    is_enabled: bool = True
    use_default_schedule: bool = True


class UpdateDockerSyncScheduleRequest(BaseModel):
    """Schema for updating a sync schedule."""

    cron_expression: str | None = None
    is_enabled: bool | None = None
    use_default_schedule: bool | None = None


class DockerSyncScheduleOut(BaseModel):
    """Schema for sync schedule response."""

    id: int
    sync_type: str
    docker_image_source_id: int
    cron_expression: str | None
    is_enabled: bool
    use_default_schedule: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──── Generic SyncSchedule (used by schedules.py for listing) ───────────────


class SyncScheduleOut(BaseModel):
    """Schema for sync schedule response (generic — covers docker and helm types)."""

    id: int
    sync_type: str  # 'docker_image', 'helm_chart'
    docker_image_source_id: int | None = None
    helm_chart_source_id: int | None = None
    cron_expression: str | None
    is_enabled: bool
    use_default_schedule: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ──── Compare ───────────────────────────────────────────────────────────────


class DockerImageTagCompareItem(BaseModel):
    """Comparison info for a single tag between two sources."""

    tag: str
    digest_a: str | None = None
    digest_b: str | None = None
    match: bool | None = None  # True=same digest, False=differ, None=only in one
    architectures_a: str | None = None
    architectures_b: str | None = None
    size_bytes_a: int | None = None
    size_bytes_b: int | None = None


class DockerImageCompareSummary(BaseModel):
    """Summary statistics for the comparison."""

    total_tags: int
    matching_tags: int
    differing_tags: int
    only_in_a: int
    only_in_b: int


class DockerImageCompareResponse(BaseModel):
    """Response for comparing tags between two Docker image sources."""

    source_a: DockerImageSourceOut
    source_b: DockerImageSourceOut
    tags: list[DockerImageTagCompareItem]
    summary: DockerImageCompareSummary
