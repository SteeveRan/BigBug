"""
@file oidc_config.py
@description Pydantic schemas for OIDC configuration — admin CRUD and public
             SSO bootstrap endpoint.
@relatedFiles ../models/oidc_config.py, ../services/oidc_config.py, ../api/auth.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from app.services.oidc import parse_realm_from_issuer


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

    @field_validator("issuer_url")
    @classmethod
    def _validate_issuer_url(cls, v: str | None) -> str | None:
        # Empty string / None are valid (SSO unconfigured); a non-empty value
        # must be a full RFC 8414 realm issuer, e.g.
        # https://kc.example.com/realms/myrealm.
        if not v:
            return v
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("issuer_url must be an absolute http(s) URL")
        if parts.query or parts.fragment:
            raise ValueError("issuer_url must not contain a query or fragment")
        if parse_realm_from_issuer(v) is None:
            raise ValueError(
                'issuer_url must be a full realm issuer URI with a "/realms/<realm>" path'
            )
        return v


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
