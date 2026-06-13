"""
@file credential.py
@description Pydantic schemas for Credential CRUD operations.
             secret is accepted as plaintext in Create/Update payloads
             and NEVER returned in Out schemas.
@dependencies pydantic, app.models.credential.CredentialType
@relatedFiles ../models/credential.py, ../core/secrets.py
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.credential import CredentialType

# ──── Credential Create ────────────────────────────────────────────────────


class CredentialCreate(BaseModel):
    """Payload to create a credential. ``secret`` is plaintext — the
    service layer encrypts it before persisting."""

    name: str = Field(..., max_length=255, description="Unique display name")
    credential_type: CredentialType
    provider: str = Field(..., max_length=50, description="github, gitlab, generic")
    username: str | None = Field(None, max_length=255)
    secret: str = Field(..., description="Token, password, or SSH private key — plaintext input")
    ssh_public_key: str | None = Field(None, description="SSH public key for SSH_KEY type")
    base_url: str | None = Field(
        None, max_length=500, description="Base URL for self-hosted instances"
    )


class CredentialUpdate(BaseModel):
    """Partial update — only supplied fields are applied. ``secret``, if
    provided, will be encrypted on save."""

    name: str | None = Field(None, max_length=255)
    username: str | None = Field(None, max_length=255)
    secret: str | None = Field(
        None, description="Token, password, or SSH private key — plaintext input"
    )
    ssh_public_key: str | None = Field(None, description="SSH public key for SSH_KEY type")
    base_url: str | None = Field(
        None, max_length=500, description="Base URL for self-hosted instances"
    )


# ──── Credential Out ───────────────────────────────────────────────────────


class CredentialOut(BaseModel):
    """Public representation — NO secret (encrypted_secret) fields."""

    id: int
    name: str
    credential_type: CredentialType
    provider: str
    username: str | None = None
    ssh_public_key: str | None = None
    base_url: str | None = None
    status_flag: int
    status_text: str | None = None
    last_tested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
