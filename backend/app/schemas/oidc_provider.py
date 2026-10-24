"""
@file oidc_provider.py
@description Pydantic schemas for OIDC providers — admin CRUD (multi-provider,
              ADR-0037) and the public SSO bootstrap endpoint.
@relatedFiles ../models/oidc_provider.py, ../services/oidc_providers.py, ../api/auth.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from app.services.oidc import parse_realm_from_issuer


def _validate_issuer_url_value(cls: type, v: str | None) -> str | None:
    """Shared issuer_url validation per ADR-0036 (full realm URI or empty)."""
    if not v:
        return v
    parts = urlsplit(v)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("issuer_url must be an absolute http(s) URL")
    if parts.query or parts.fragment:
        raise ValueError("issuer_url must not contain a query or fragment")
    if parse_realm_from_issuer(v) is None:
        raise ValueError('issuer_url must be a full realm issuer URI with a "/realms/<realm>" path')
    return v


class OIDCProviderCreate(BaseModel):
    """Admin POST payload — name is the only required field."""

    name: str = Field(min_length=1, max_length=255)
    issuer_url: str = ""
    client_id: str = ""
    client_secret: str | None = None
    frontend_client_id: str = ""
    enabled: bool = False
    public_url: str | None = None
    role_mapping: dict[str, str] = Field(default_factory=dict)
    sort_order: int = 0

    _validate_issuer = field_validator("issuer_url")(classmethod(_validate_issuer_url_value))


class OIDCProviderUpdate(BaseModel):
    """Admin PATCH payload — every field is optional."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    frontend_client_id: str | None = None
    enabled: bool | None = None
    public_url: str | None = None
    role_mapping: dict[str, str] | None = None
    sort_order: int | None = None

    _validate_issuer = field_validator("issuer_url")(classmethod(_validate_issuer_url_value))


class OIDCProviderOut(BaseModel):
    """
    Full provider row returned to admin callers.

    ``client_secret`` is never exposed — the field always shows ``********``
    so the response is safe to return even when the secret is populated.
    """

    id: int
    name: str
    issuer_url: str
    client_id: str
    client_secret: str = "********"
    frontend_client_id: str
    enabled: bool
    public_url: str | None
    role_mapping: dict[str, str] = Field(default_factory=dict)
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("client_secret", mode="before")
    @classmethod
    def _mask_secret(cls, v: Any) -> str:
        # Always mask — the real encrypted value is never returned via API.
        return "********"


class SSOProvider(BaseModel):
    """One public entry of the SSO bootstrap list — one frontend button."""

    id: int
    name: str
    url: str
    realm: str
    client_id: str


class SSOConfig(BaseModel):
    """
    Public OIDC bootstrap the frontend needs (list contract, ADR-0037):
    one button per entry in ``providers``. ``enabled`` is the global
    master-switch — when off, the list is empty.
    """

    enabled: bool
    providers: list[SSOProvider]
