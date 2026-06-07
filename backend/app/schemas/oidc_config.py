"""
@file oidc_config.py
@description Pydantic schemas for OIDC configuration — admin CRUD and public
             SSO bootstrap endpoint.
@relatedFiles ../models/oidc_config.py, ../services/oidc_config.py, ../api/auth.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class OIDCConfigOut(BaseModel):
    """
    Full configuration returned to admin callers.

    ``client_secret`` is never exposed — the field always shows ``********``
    so the response is safe to return even when the secret is populated.
    """

    id: int
    issuer_url: str
    client_id: str
    client_secret: str = "********"
    frontend_client_id: str
    enabled: bool
    public_url: str | None
    role_mapping: dict[str, str] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("client_secret", mode="before")
    @classmethod
    def _mask_secret(cls, v: Any) -> str:
        # Always mask — the real encrypted value is never returned via API.
        return "********"


class OIDCConfigUpdate(BaseModel):
    """Admin PATCH payload — every field is optional."""

    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    frontend_client_id: str | None = None
    enabled: bool | None = None
    public_url: str | None = None
    role_mapping: dict[str, str] | None = None


class OIDCConfigPublic(BaseModel):
    """
    Minimal subset the frontend SSO button needs to bootstrap keycloak-js.

    Deliberately *not* a subclass of OIDCConfigOut so changes to the admin
    schema never accidentally leak fields to unauthenticated callers.
    """

    enabled: bool
    issuer_url: str
    frontend_client_id: str
    public_url: str | None
