"""
@file integrations.py
@description Pydantic schemas for GitLab, Harbor, and GitHub instance management.
             Secrets (tokens/passwords) are accepted as plaintext in Create/Update
             payloads and NEVER returned in Out schemas.
@dependencies pydantic
@relatedFiles ../models/gitlab_instance.py, ../models/harbor_instance.py,
              ../models/github_instance.py
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Shared validators for Out schemas
# ---------------------------------------------------------------------------


class _DatetimeStrOut(BaseModel):
    """Base mixin that converts datetime→isoformat for Out schemas."""

    @field_validator(
        "created_at",
        "updated_at",
        "last_checked_at",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def _dt_to_iso(cls, v: object) -> str | None:
        if isinstance(v, datetime):
            return v.isoformat()
        return v  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# GitLab Instance
# ---------------------------------------------------------------------------


class GitlabInstanceCreate(BaseModel):
    """Payload to create a GitLab instance. ``token`` is plaintext — the
    service layer encrypts it before persisting."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique display name")
    url: str = Field(
        ..., min_length=1, max_length=512, description="Base URL e.g. https://gitlab.example.com"
    )
    token: str | None = Field(None, description="Personal Access Token or OAuth token")
    is_active: bool = Field(True)
    verify_ssl: bool = Field(True)
    is_default: bool = Field(False)
    default_group_id: int | None = Field(None)


class GitlabInstanceUpdate(BaseModel):
    """Partial update — only supplied fields are applied. ``token``, if
    provided, will be encrypted on save."""

    name: str | None = Field(None, min_length=1, max_length=255)
    url: str | None = Field(None, min_length=1, max_length=512)
    token: str | None = None
    is_active: bool | None = None
    verify_ssl: bool | None = None
    is_default: bool | None = None
    default_group_id: int | None = None


class GitlabInstanceOut(_DatetimeStrOut):
    """Public representation — NO secret fields."""

    id: int
    name: str
    url: str
    is_active: bool
    status_flag: int
    status_text: str
    created_at: str
    updated_at: str
    verify_ssl: bool
    is_default: bool
    default_group_id: int | None
    last_checked_at: str | None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Harbor Instance
# ---------------------------------------------------------------------------


class HarborInstanceCreate(BaseModel):
    """Payload to create a Harbor instance. ``password`` is plaintext — the
    service layer encrypts it before persisting."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique display name")
    url: str = Field(
        ..., min_length=1, max_length=512, description="Base URL e.g. https://harbor.example.com"
    )
    username: str = Field(..., min_length=1, max_length=255)
    password: str | None = Field(None, description="User password or robot account secret")
    is_active: bool = Field(True)
    verify_ssl: bool = Field(True)
    is_default: bool = Field(False)
    default_project: str | None = Field(None)


class HarborInstanceUpdate(BaseModel):
    """Partial update — only supplied fields are applied. ``password``, if
    provided, will be encrypted on save."""

    name: str | None = Field(None, min_length=1, max_length=255)
    url: str | None = Field(None, min_length=1, max_length=512)
    username: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = None
    is_active: bool | None = None
    verify_ssl: bool | None = None
    is_default: bool | None = None
    default_project: str | None = None


class HarborInstanceOut(_DatetimeStrOut):
    """Public representation — NO secret fields."""

    id: int
    name: str
    url: str
    username: str
    is_active: bool
    status_flag: int
    status_text: str
    created_at: str
    updated_at: str
    verify_ssl: bool
    is_default: bool
    default_project: str | None
    last_checked_at: str | None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# GitHub Instance
# ---------------------------------------------------------------------------


class GithubInstanceCreate(BaseModel):
    """Payload to create a GitHub instance. ``token`` is plaintext — the
    service layer encrypts it before persisting."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique display name")
    token: str | None = Field(None, description="Personal Access Token (classic or fine-grained)")
    is_active: bool = Field(True)
    is_default: bool = Field(False)


class GithubInstanceUpdate(BaseModel):
    """Partial update — only supplied fields are applied. ``token``, if
    provided, will be encrypted on save."""

    name: str | None = Field(None, min_length=1, max_length=255)
    token: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None


class GithubInstanceOut(_DatetimeStrOut):
    """Public representation — NO secret fields."""

    id: int
    name: str
    is_active: bool
    status_flag: int
    status_text: str
    created_at: str
    updated_at: str
    is_default: bool
    last_checked_at: str | None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Docker Registry Instance
# ---------------------------------------------------------------------------


class DockerRegistryInstanceCreate(BaseModel):
    """Payload to create a Docker Registry instance. ``password`` is plaintext —
    the service layer encrypts it before persisting."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique display name")
    url: str = Field(
        ..., min_length=1, max_length=500, description="Registry URL e.g. registry.example.com"
    )
    username: str | None = Field(None, description="Registry username")
    password: str | None = Field(None, description="Registry password or token")
    is_active: bool = Field(True)
    is_default: bool = Field(False)
    verify_ssl: bool = Field(True)
    registry_type: str = Field(
        "external",
        description="Classification: internal (company registries) or external (third-party)",
    )
    registry_provider: str = Field(
        "generic",
        description=(
            "Known registry provider for auto-detection: "
            "docker_hub, quay_io, gcr, ecr, acr, ghcr, harbor, generic"
        ),
    )
    priority: int = Field(0, description="Higher priority = preferred for auto-selection")


class DockerRegistryInstanceUpdate(BaseModel):
    """Partial update — only supplied fields are applied. ``password``, if
    provided, will be encrypted on save."""

    name: str | None = Field(None, min_length=1, max_length=255)
    url: str | None = Field(None, min_length=1, max_length=500)
    username: str | None = None
    password: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None
    verify_ssl: bool | None = None
    registry_type: str | None = None
    registry_provider: str | None = None
    priority: int | None = None


class DockerRegistryInstanceOut(_DatetimeStrOut):
    """Public representation — NO secret fields."""

    id: int
    name: str
    url: str
    username: str | None
    is_active: bool
    is_default: bool
    verify_ssl: bool
    registry_type: str
    registry_provider: str
    priority: int
    status_flag: int
    status_text: str
    last_checked_at: str | None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Helm Repository Instance
# ---------------------------------------------------------------------------


class HelmRepositoryInstanceCreate(BaseModel):
    """Payload to create a Helm Repository instance. ``password`` is plaintext —
    the service layer encrypts it before persisting."""

    name: str = Field(..., min_length=1, max_length=255, description="Unique display name")
    url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Repository URL e.g. https://charts.example.com",
    )
    username: str | None = Field(None, description="Repository username")
    password: str | None = Field(None, description="Repository password or token")
    is_active: bool = Field(True)
    is_default: bool = Field(False)
    verify_ssl: bool = Field(True)


class HelmRepositoryInstanceUpdate(BaseModel):
    """Partial update — only supplied fields are applied. ``password``, if
    provided, will be encrypted on save."""

    name: str | None = Field(None, min_length=1, max_length=255)
    url: str | None = Field(None, min_length=1, max_length=500)
    username: str | None = None
    password: str | None = None
    is_active: bool | None = None
    is_default: bool | None = None
    verify_ssl: bool | None = None


class HelmRepositoryInstanceOut(_DatetimeStrOut):
    """Public representation — NO secret fields."""

    id: int
    name: str
    url: str
    username: str | None
    is_active: bool
    is_default: bool
    verify_ssl: bool
    status_flag: int
    status_text: str
    last_checked_at: str | None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------


class ConnectionTestResult(BaseModel):
    """Result of a ``POST /test`` connection check."""

    success: bool
    message: str
    status_code: int | None = None  # HTTP status from the remote, if applicable
