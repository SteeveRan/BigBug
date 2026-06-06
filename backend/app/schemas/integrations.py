"""
@file integrations.py
@description Pydantic schemas for GitLab, Harbor, and GitHub instance management.
             Secrets (tokens/passwords) are accepted as plaintext in Create/Update
             payloads and NEVER returned in Out schemas.
@dependencies pydantic
@relatedFiles ../models/gitlab_instance.py, ../models/harbor_instance.py,
              ../models/github_instance.py
"""

from pydantic import BaseModel, ConfigDict, Field

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


class GitlabInstanceUpdate(BaseModel):
    """Partial update — only supplied fields are applied. ``token``, if
    provided, will be encrypted on save."""

    name: str | None = Field(None, min_length=1, max_length=255)
    url: str | None = Field(None, min_length=1, max_length=512)
    token: str | None = None
    is_active: bool | None = None


class GitlabInstanceOut(BaseModel):
    """Public representation — NO secret fields."""

    id: int
    name: str
    url: str
    is_active: bool
    status_flag: int
    status_text: str
    created_at: str
    updated_at: str

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


class HarborInstanceUpdate(BaseModel):
    """Partial update — only supplied fields are applied. ``password``, if
    provided, will be encrypted on save."""

    name: str | None = Field(None, min_length=1, max_length=255)
    url: str | None = Field(None, min_length=1, max_length=512)
    username: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = None
    is_active: bool | None = None


class HarborInstanceOut(BaseModel):
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


class GithubInstanceUpdate(BaseModel):
    """Partial update — only supplied fields are applied. ``token``, if
    provided, will be encrypted on save."""

    name: str | None = Field(None, min_length=1, max_length=255)
    token: str | None = None
    is_active: bool | None = None


class GithubInstanceOut(BaseModel):
    """Public representation — NO secret fields."""

    id: int
    name: str
    is_active: bool
    status_flag: int
    status_text: str
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
