"""
@file source_provider.py
@description Pydantic schemas for SourceProvider CRUD operations.
@dependencies pydantic, app.models.source_provider.ProviderType
@relatedFiles ../models/source_provider.py, ./credential.py
"""

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.models.source_provider import ProviderType

if TYPE_CHECKING:
    from app.schemas.credential import CredentialOut


# ──── SourceProvider Create ────────────────────────────────────────────────


class SourceProviderCreate(BaseModel):
    """Payload to create a source provider."""

    credential_id: int | None = Field(None, description="Optional FK to Credential for auth")
    provider_type: ProviderType = Field(..., description="github, gitlab, generic")
    label: str = Field(..., max_length=255, description="e.g. 'github.com (org-token)'")


# ──── SourceProvider Out ───────────────────────────────────────────────────


class SourceProviderOut(BaseModel):
    """Public representation of a source provider."""

    id: int
    credential_id: int | None = None
    provider_type: ProviderType
    label: str
    is_deleted: bool
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    credential: CredentialOut | None = None

    model_config = {"from_attributes": True}
