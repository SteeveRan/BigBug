"""
@file gitlab_project.py
@description Pydantic schemas for GitlabProject CRUD, file/tag/share/sync/import
              operations and component presets. Follows the provider schema style
              (``from_attributes`` for Out models, enum-typed fields for the
              in-models).
@dependencies pydantic, app.models.gitlab_project
@relatedFiles ../models/gitlab_project.py, ../services/gitlab_projects/,
               ../api/gitlab_projects.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.gitlab_project import GitlabProjectType, ProjectVisibility

# ──── Create / Update ──────────────────────────────────────────────────────


class GitlabProjectCreate(BaseModel):
    """Payload to create a GitLab project via the GitLab API."""

    name: str = Field(..., max_length=255, description="Display name in GitLab")
    path: str = Field(..., max_length=255, description="Project slug")
    namespace_path: str = Field(..., max_length=500, description="Group or personal namespace")
    project_type: GitlabProjectType
    provider_id: int
    gitlab_visibility: str = Field("private", max_length=32)
    default_branch: str = Field("main", max_length=255)
    description: str | None = None
    visibility: ProjectVisibility = ProjectVisibility.owner
    team_id: int | None = None
    initialize_with_readme: bool = True
    create_namespace: bool = False

    @model_validator(mode="after")
    def _validate_team_visibility(self) -> GitlabProjectCreate:
        if self.visibility == ProjectVisibility.team and self.team_id is None:
            raise ValueError("team_id is required when visibility is 'team'")
        return self


class GitlabProjectUpdate(BaseModel):
    """Partial update — only supplied fields are applied."""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    visibility: ProjectVisibility | None = None
    team_id: int | None = None
    gitlab_visibility: str | None = Field(None, max_length=32)
    default_branch: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def _validate_team_visibility(self) -> GitlabProjectUpdate:
        if self.visibility == ProjectVisibility.team and self.team_id is None:
            raise ValueError("team_id is required when visibility is 'team'")
        return self


class GitlabProjectImport(BaseModel):
    """Register an existing GitLab project (no mutations in GitLab)."""

    provider_id: int
    full_path: str = Field(..., max_length=512)
    project_type: GitlabProjectType
    visibility: ProjectVisibility = ProjectVisibility.owner
    team_id: int | None = None


class GitlabProjectShareIn(BaseModel):
    """Body for POST /api/gitlab-projects/{id}/share."""

    team_id: int


# ──── Out ──────────────────────────────────────────────────────────────────


class GitlabProjectOut(BaseModel):
    """Public representation of a GitlabProject."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    path: str
    namespace_path: str
    full_path: str
    project_type: GitlabProjectType
    visibility: ProjectVisibility
    provider_id: int
    external_id: str | None = None
    web_url: str | None = None
    default_branch: str
    gitlab_visibility: str | None = None
    description: str | None = None
    owner_user_id: int | None = None
    team_id: int | None = None
    status_flag: int
    status_text: str | None = None
    last_synced_at: datetime | None = None
    is_deleted: bool
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ──── Files / tags ─────────────────────────────────────────────────────────


class GitlabProjectFileIn(BaseModel):
    """Body for upserting a file into a GitLab project."""

    file_path: str = Field(..., max_length=1024)
    content: str
    branch: str | None = None
    commit_message: str | None = None
    encoding: str = Field("text", description="text or base64")


class GitlabProjectFileOut(BaseModel):
    """A single repository file/tree entry."""

    path: str
    type: str | None = None  # "blob" | "tree"
    content: str | None = None
    size: int | None = None
    ref: str | None = None


class GitlabProjectTagIn(BaseModel):
    """Body for creating a GitLab tag (component version)."""

    tag_name: str = Field(..., max_length=255)
    ref: str | None = None
    message: str | None = None


class GitlabProjectTagOut(BaseModel):
    """A single GitLab tag."""

    name: str
    target: str | None = None
    message: str | None = None
    created_at: datetime | None = None


class GitlabProjectSyncResult(BaseModel):
    """Result of a metadata sync from GitLab."""

    id: int
    status_flag: int
    status_text: str | None = None
    external_id: str | None = None
    web_url: str | None = None
    default_branch: str | None = None
    gitlab_visibility: str | None = None
    last_synced_at: datetime | None = None


# ──── Component presets ────────────────────────────────────────────────────


class ComponentPresetOut(BaseModel):
    """Serialised component template metadata for the UI preset selector."""

    key: str
    name: str
    description: str
    inputs_schema: dict[str, Any] = Field(default_factory=dict)


class ComponentPushIn(BaseModel):
    """Body for pushing/updating a component's content in GitLab."""

    content: str
    file_path: str | None = None
    commit_message: str | None = None
    tag_name: str | None = None


class ComponentPullOut(BaseModel):
    """Result of pulling a component's current content from GitLab."""

    file_path: str
    content: str
    ref: str | None = None


class PipelinePushCiIn(BaseModel):
    """Body for generating and pushing ``.gitlab-ci.yml`` from a Pipeline config."""

    commit_message: str | None = None
    extra_yaml: str | None = None
