"""
@file trust_store.py
@description Pydantic schemas for the Trust Store API (ADR-0037). PEM contents
              are public CA certificates (not secrets) and are returned in the
              certificate schemas for display.
@dependencies pydantic
@relatedFiles ../models/trust_store.py, ../services/trust_store.py, ../api/trust_stores.py
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrustStoreCertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    pem: str
    fingerprint: str
    created_at: datetime


class TrustStoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    certificates: list[TrustStoreCertificateOut] = Field(default_factory=list)


class TrustStoreCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class TrustStoreUpdate(BaseModel):
    """Partial update — only supplied fields are applied."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None


class TrustStoreCertificateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    # One PEM text may contain several BEGIN CERTIFICATE blocks — a chain is
    # split into separate certificate rows by the service.
    pem: str = Field(..., min_length=1)


class TrustStoreCertificatesIn(BaseModel):
    """Body for POST /{id}/certificates: either a single {name, pem} or a list."""

    name: str | None = Field(None, min_length=1, max_length=255)
    pem: str | None = None
    certificates: list[TrustStoreCertificateIn] | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> TrustStoreCertificatesIn:
        if self.certificates:
            return self
        if self.name and self.pem:
            return self
        raise ValueError(
            "provide either {'name', 'pem'} or {'certificates': [{'name', 'pem'}, ...]}"
        )

    def items(self) -> list[TrustStoreCertificateIn]:
        """Normalised list of certificates to add."""
        if self.certificates:
            return self.certificates
        return [TrustStoreCertificateIn(name=self.name or "", pem=self.pem or "")]


class TrustStoreUsageOut(BaseModel):
    trust_store_id: int
    providers: list[str] = Field(default_factory=list)
