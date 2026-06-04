from datetime import datetime
from pydantic import BaseModel


class GitlabMirrorOut(BaseModel):
    id: int
    project_id: int
    gitlab_project_id: str | None
    gitlab_namespace: str | None
    gitlab_url: str
    gitlab_name: str | None
    mirrored_branch: str
    last_synced_release_tag: str | None
    last_sync_at: datetime | None
    status_flag: int
    status_text: str | None
    is_imported: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateMirrorRequest(BaseModel):
    project_id: int
    gitlab_url: str
    mirrored_branch: str = "main"
    pipeline_trigger_token: str | None = None


class ImportMirrorRequest(BaseModel):
    github_url: str
    gitlab_url: str


class UpdateMirrorRequest(BaseModel):
    mirrored_branch: str | None = None
    pipeline_trigger_token: str | None = None


class SyncLogOut(BaseModel):
    id: int
    mirror_id: int
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


class SyncScheduleOut(BaseModel):
    id: int
    mirror_id: int
    cron_expression: str | None
    is_enabled: bool
    use_default_schedule: bool
    next_run_at: datetime | None
    last_run_at: datetime | None

    model_config = {"from_attributes": True}


class UpdateSyncScheduleRequest(BaseModel):
    cron_expression: str | None = None
    is_enabled: bool | None = None
    use_default_schedule: bool | None = None
