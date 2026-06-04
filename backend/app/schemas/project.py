from datetime import datetime
from pydantic import BaseModel


class GithubOrgOut(BaseModel):
    id: int
    login: str
    type: str
    avatar_url: str | None
    github_id: int | None

    model_config = {"from_attributes": True}


class GithubReleaseOut(BaseModel):
    id: int
    tag_name: str
    name: str | None
    is_prerelease: bool
    is_draft: bool
    published_at: datetime | None

    model_config = {"from_attributes": True}


class GithubProjectOut(BaseModel):
    id: int
    org_id: int
    org: GithubOrgOut
    name: str
    full_name: str
    github_url: str
    description: str | None
    custom_description: str | None
    readme_md: str | None
    default_branch: str
    homepage_url: str | None
    license_spdx: str | None
    license_name: str | None
    is_archived: bool
    is_fork: bool
    is_stale: bool
    stale_threshold_days: int
    last_synced_at: datetime | None
    github_created_at: datetime | None
    github_updated_at: datetime | None
    github_pushed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GithubProjectListOut(BaseModel):
    id: int
    org: GithubOrgOut
    name: str
    full_name: str
    github_url: str
    description: str | None
    custom_description: str | None
    license_spdx: str | None
    is_archived: bool
    is_stale: bool
    last_synced_at: datetime | None
    github_updated_at: datetime | None

    model_config = {"from_attributes": True}


class ImportProjectRequest(BaseModel):
    github_url: str
    gitlab_url: str | None = None


class CreateProjectRequest(BaseModel):
    github_url: str


class UpdateProjectRequest(BaseModel):
    custom_description: str | None = None
    stale_threshold_days: int | None = None
