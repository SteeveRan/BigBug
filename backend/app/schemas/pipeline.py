"""
@file pipeline.py
@description Pydantic schemas for PipelineRun and GitLabComponent CRUD operations.
@dependencies pydantic
@relatedFiles ../models/pipeline_run.py, ../models/gitlab_component.py,
               ../../services/pipeline.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# ──────────────────────────────────────────────────────────────────────
# Pipeline Run Schemas
# ──────────────────────────────────────────────────────────────────────


class PipelineRunCreate(BaseModel):
    """Payload for triggering a new pipeline run."""

    gitlab_instance_id: int
    gitlab_project_id: int
    ref: str = Field(..., description="Branch, tag, or commit SHA")
    variables: dict[str, str] = Field(default_factory=dict)


class PipelineRunOut(BaseModel):
    """Response schema for a pipeline run."""

    id: int
    gitlab_instance_id: int
    gitlab_project_id: int
    gitlab_pipeline_id: int | None
    component_id: int | None  # Added for component runs
    triggered_by_user_id: int | None
    trigger_type: str
    ref: str
    variables: dict[str, Any]
    status_flag: int
    status_text: str
    duration: int | None
    web_url: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class PipelineRunList(BaseModel):
    """Paginated list of pipeline runs."""

    items: list[PipelineRunOut]
    total: int
    page: int
    page_size: int


# ──────────────────────────────────────────────────────────────────────
# GitLab Component Schemas
# ──────────────────────────────────────────────────────────────────────


class GitLabComponentCreate(BaseModel):
    """Payload for registering a new GitLab CI/CD component."""

    name: str = Field(..., max_length=255)
    description: str | None = None
    gitlab_instance_id: int
    project_path: str = Field(..., max_length=512)
    component_path: str = Field(..., max_length=512)
    version: str | None = Field(None, max_length=64)
    inputs_schema: dict[str, Any] | None = None


class GitLabComponentUpdate(BaseModel):
    """Partial update payload for a GitLab component."""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    gitlab_instance_id: int | None = None
    project_path: str | None = Field(None, max_length=512)
    component_path: str | None = Field(None, max_length=512)
    version: str | None = Field(None, max_length=64)
    inputs_schema: dict[str, Any] | None = None
    is_enabled: bool | None = None


class GitLabComponentOut(BaseModel):
    """Response schema for a GitLab component."""

    id: int
    name: str
    description: str | None
    gitlab_instance_id: int
    project_path: str
    component_path: str
    version: str | None
    inputs_schema: dict[str, Any] | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ComponentRunRequest(BaseModel):
    """Payload for running a GitLab CI/CD component pipeline."""

    ref: str = Field("main", description="Branch, tag, or commit SHA")
    inputs: dict[str, str] = Field(default_factory=dict, description="Component input variables")
