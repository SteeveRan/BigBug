from datetime import datetime

from pydantic import BaseModel


class GoldImageOut(BaseModel):
    id: int
    name: str
    os_family: str
    description: str | None
    dockerfile: str | None
    gitlab_project_id: str | None
    gitlab_project_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateGoldImageRequest(BaseModel):
    name: str
    os_family: str
    description: str | None = None
    dockerfile: str | None = None
    gitlab_project_id: str | None = None
    gitlab_project_url: str | None = None


class UpdateGoldImageRequest(BaseModel):
    description: str | None = None
    dockerfile: str | None = None
    gitlab_project_id: str | None = None
    gitlab_project_url: str | None = None


class AppImageOut(BaseModel):
    id: int
    project_id: int | None
    gold_image_id: int | None
    name: str
    description: str | None
    dockerfile: str | None
    gitlab_project_id: str | None
    gitlab_project_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateAppImageRequest(BaseModel):
    project_id: int | None = None
    gold_image_id: int | None = None
    name: str
    description: str | None = None
    dockerfile: str | None = None
    gitlab_project_id: str | None = None
    gitlab_project_url: str | None = None


class UpdateAppImageRequest(BaseModel):
    description: str | None = None
    dockerfile: str | None = None
    gold_image_id: int | None = None
    gitlab_project_id: str | None = None
    gitlab_project_url: str | None = None


class ImageVersionOut(BaseModel):
    id: int
    image_type: str
    gold_image_id: int | None
    app_image_id: int | None
    version_tag: str
    arch: str
    registry_url: str | None
    sha256_digest: str | None
    cosign_signature: str | None
    is_signed: bool
    status_flag: int
    status_text: str | None
    built_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateImageVersionRequest(BaseModel):
    version_tag: str
    arch: str = "amd64"


class BuildLogOut(BaseModel):
    id: int
    image_version_id: int
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


class BuildScheduleOut(BaseModel):
    id: int
    image_type: str
    gold_image_id: int | None
    app_image_id: int | None
    is_enabled: bool
    use_default_schedule: bool
    cron_expression: str | None
    next_run_at: datetime | None
    last_run_at: datetime | None

    model_config = {"from_attributes": True}


class UpdateBuildScheduleRequest(BaseModel):
    is_enabled: bool | None = None
    use_default_schedule: bool | None = None
    cron_expression: str | None = None
