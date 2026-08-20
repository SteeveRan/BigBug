from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
    chart_name: str | None
    chart_version: str | None
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
    provider_id: int | None = None
    gitlab_project_id: str | None
    gitlab_project_url: str | None
    target_repo_url: str | None = None
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
    provider_id: int | None = None  # helm/helm_repo/external provider (V3)
    target_repo_url: str | None = None  # target repo where charts are mirrored


class UpdateHelmChartSourceRequest(BaseModel):
    name: str | None = None
    repo_url: str | None = None
    description: str | None = None
    provider_id: int | None = None
    target_repo_url: str | None = None
    gitlab_project_id: str | None = None
    gitlab_project_url: str | None = None


# ──── Sync Schedule ─────────────────────────────────────────────────────────


class CreateHelmSyncScheduleRequest(BaseModel):
    """Schema for creating a sync schedule for a Helm chart source."""

    cron_expression: str | None = None
    is_enabled: bool = True
    use_default_schedule: bool = True


class UpdateHelmSyncScheduleRequest(BaseModel):
    """Schema for updating a sync schedule."""

    cron_expression: str | None = None
    is_enabled: bool | None = None
    use_default_schedule: bool | None = None


class HelmSyncScheduleOut(BaseModel):
    """Schema for sync schedule response."""

    id: int
    sync_type: str
    helm_chart_source_id: int
    cron_expression: str | None
    is_enabled: bool
    use_default_schedule: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
