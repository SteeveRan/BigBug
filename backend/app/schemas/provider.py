"""
@file provider.py
@description Pydantic schemas for the unified Providers V3 API. Secrets are never
             accepted in ``config`` (deny-list + per-subtype JSON Schema) and never
             returned in ``ProviderOut``.
@dependencies pydantic, app.models.resource_provider, app.services.providers.registry
@relatedFiles ../models/resource_provider.py, ../services/providers/registry.py
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ProviderVisibility,
)
from app.services.providers.registry import get_spec

# ──── Config deny-list (11.1.2) ────────────────────────────────────────────

_DENY_EXACT_KEYS = {
    "token",
    "password",
    "secret",
    "key",
    "auth",
    "private_key",
    "credential",
}
_DENY_SUFFIXES = ("_token", "_password", "_secret", "_key", "_credentials")


def _deny_secret_keys(config: dict[str, Any]) -> None:
    """Reject any key that names a secret (defense-in-depth, 11.1.2)."""
    for key in config:
        lowered = key.lower()
        if lowered in _DENY_EXACT_KEYS or lowered.endswith(_DENY_SUFFIXES):
            raise ValueError(f"secret-like key '{key}' is not allowed in provider config")


def _validate_config_for_subtype(subtype: ProviderSubtype, config: dict[str, Any]) -> None:
    """Validate ``config`` against the registry JSON Schema for ``subtype``."""
    spec = get_spec(subtype)
    allowed = set(spec.config_schema.get("properties", {}).keys())
    unknown = set(config) - allowed
    if unknown:
        raise ValueError(f"unknown config key(s) for subtype '{subtype.value}': {sorted(unknown)}")
    _deny_secret_keys(config)


# ──── ProviderConfigIn ─────────────────────────────────────────────────────


class ProviderConfigIn(BaseModel):
    """Provider ``config`` payload. Validated per-subtype against the registry
    JSON Schema, with ``additionalProperties`` forbidden and a secret deny-list."""

    model_config = ConfigDict(extra="forbid")

    subtype: ProviderSubtype
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> ProviderConfigIn:
        _validate_config_for_subtype(self.subtype, self.config)
        return self


# ──── Provider Create / Update ─────────────────────────────────────────────


class ProviderCreate(BaseModel):
    """Payload to create a resource provider."""

    domain: ProviderDomain
    subtype: ProviderSubtype
    category: ProviderCategory
    direction: ProviderDirection
    name: str = Field(..., max_length=255)
    label: str = Field(..., max_length=255)
    description: str | None = None
    base_url: str | None = Field(None, max_length=500)
    config: dict[str, Any] = Field(default_factory=dict)
    credential_id: int | None = None
    visibility: ProviderVisibility = ProviderVisibility.owner
    team_id: int | None = None

    @model_validator(mode="after")
    def _validate_by_registry(self) -> ProviderCreate:
        spec = get_spec(self.subtype)
        if self.domain != spec.domain:
            raise ValueError(
                f"subtype '{self.subtype.value}' belongs to domain '{spec.domain.value}'"
            )
        if self.category not in spec.allowed_categories:
            raise ValueError(
                f"category '{self.category.value}' not allowed for subtype '{self.subtype.value}'"
            )
        if self.direction not in spec.allowed_directions:
            raise ValueError(
                f"direction '{self.direction.value}' not allowed for subtype '{self.subtype.value}'"
            )
        if self.base_url is None and spec.requires_base_url:
            raise ValueError(f"base_url is required for subtype '{self.subtype.value}'")
        _validate_config_for_subtype(self.subtype, self.config)
        return self

    @model_validator(mode="after")
    def _validate_visibility(self) -> ProviderCreate:
        if self.visibility == ProviderVisibility.team and self.team_id is None:
            raise ValueError("team_id is required when visibility is 'team'")
        if (
            self.category == ProviderCategory.system
            and self.visibility == ProviderVisibility.public
        ):
            raise ValueError("system providers cannot have public visibility")
        return self


class ProviderUpdate(BaseModel):
    """Partial update — only supplied fields are applied."""

    category: ProviderCategory | None = None
    direction: ProviderDirection | None = None
    label: str | None = Field(None, max_length=255)
    description: str | None = None
    base_url: str | None = Field(None, max_length=500)
    config: dict[str, Any] | None = None
    credential_id: int | None = None
    is_active: bool | None = None
    is_default: bool | None = None
    verify_ssl: bool | None = None
    priority: int | None = None
    visibility: ProviderVisibility | None = None
    team_id: int | None = None

    @model_validator(mode="after")
    def _validate_config_deny(self) -> ProviderUpdate:
        if self.config is not None:
            _deny_secret_keys(self.config)
        return self

    @model_validator(mode="after")
    def _validate_visibility(self) -> ProviderUpdate:
        if self.visibility == ProviderVisibility.team and self.team_id is None:
            raise ValueError("team_id is required when visibility is 'team'")
        return self


# ──── Provider Out ─────────────────────────────────────────────────────────


class ProviderOut(BaseModel):
    """Public representation — never exposes secrets or credential details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: ProviderDomain
    subtype: ProviderSubtype
    category: ProviderCategory
    direction: ProviderDirection
    name: str
    label: str
    description: str | None = None
    base_url: str | None = None
    config: dict[str, Any]
    credential_id: int | None = None
    owner_user_id: int | None = None
    visibility: ProviderVisibility = ProviderVisibility.owner
    team_id: int | None = None
    team_name: str | None = None
    is_active: bool
    is_default: bool
    is_protected: bool
    verify_ssl: bool
    priority: int
    status_flag: int
    status_text: str | None = None
    last_checked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_credential(self) -> bool:
        return self.credential_id is not None


# ──── Registry type metadata ───────────────────────────────────────────────


class ProviderTypeOut(BaseModel):
    """Serialised registry metadata for one subtype."""

    subtype: str
    domain: str
    label: str
    capabilities: list[str]
    allowed_categories: list[str]
    allowed_directions: list[str]
    allowed_credential_types: list[str]
    config_schema: dict[str, Any]
    oci_compliant: bool
    requires_base_url: bool


# ──── Test / Action ────────────────────────────────────────────────────────


class ProviderTestResult(BaseModel):
    """Result of a provider connection test."""

    ok: bool
    status_flag: int
    status_text: str | None = None


class ProviderShareIn(BaseModel):
    """Body for POST /api/providers/{id}/share (12.3)."""

    team_id: int


class ProviderActionIn(BaseModel):
    """Optional parameters for a domain action."""

    params: dict[str, Any] = Field(default_factory=dict)


class ProviderActionOut(BaseModel):
    """Result of a dispatched provider action."""

    action: str
    items: list[dict[str, Any]] = Field(default_factory=list)
