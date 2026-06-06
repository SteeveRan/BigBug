from datetime import datetime

from pydantic import BaseModel

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
    gitlab_project_id: str | None
    gitlab_project_url: str | None
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


class UpdateDockerImageSourceRequest(BaseModel):
    name: str | None = None
    registry_url: str | None = None
    description: str | None = None
