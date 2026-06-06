from datetime import datetime

from pydantic import BaseModel

# ──── HelmChartVersion ────────────────────────────────────────────────────


class HelmChartVersionOut(BaseModel):
    id: int
    source_id: int
    chart_name: str
    version: str
    app_version: str | None
    description: str | None
    digest: str | None
    chart_url: str | None
    is_synced: bool
    status_flag: int
    status_text: str | None
    last_synced_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ──── HelmSyncLog ─────────────────────────────────────────────────────────


class HelmSyncLogOut(BaseModel):
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


# ──── HelmChartSource ─────────────────────────────────────────────────────


class HelmChartSourceOut(BaseModel):
    id: int
    name: str
    repo_url: str
    description: str | None
    gitlab_project_id: str | None
    gitlab_project_url: str | None
    last_synced_at: datetime | None
    status_flag: int
    status_text: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HelmChartSourceDetailOut(HelmChartSourceOut):
    versions: list[HelmChartVersionOut] = []

    model_config = {"from_attributes": True}


# ──── Requests ────────────────────────────────────────────────────────────


class CreateHelmChartSourceRequest(BaseModel):
    name: str
    repo_url: str
    description: str | None = None


class UpdateHelmChartSourceRequest(BaseModel):
    name: str | None = None
    repo_url: str | None = None
    description: str | None = None
