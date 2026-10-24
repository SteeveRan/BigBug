"""
@file oidc_provider.py
@description One OIDC/SSO identity provider (multi-provider, ADR-0037). Replaces
              the former singleton `oidc_config` table: admins register several
              Keycloak (or other realm-style OIDC) setups, the frontend renders
              one SSO button per enabled provider. The client_secret is
              encrypted at rest via Fernet.
@dependencies app.database.Base, app.core.secrets (via service layer)
@relatedFiles ../../services/oidc_providers.py, ../schemas/oidc_provider.py
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON

from app.database import Base


class OIDCProvider(Base):
    __tablename__ = "oidc_providers"

    id = Column(Integer, primary_key=True, index=True)
    # Display name for the SSO button (e.g. "Corporate Keycloak").
    name = Column(String(255), nullable=False)
    issuer_url = Column(String(512), nullable=False, default="")
    client_id = Column(String(255), nullable=False, default="")
    client_secret = Column(Text, nullable=True)  # Fernet-encrypted at rest
    frontend_client_id = Column(String(255), nullable=False, default="")
    enabled = Column(Boolean, default=False, nullable=False)
    public_url = Column(String(512), nullable=True)
    role_mapping = Column(JSON, nullable=False, default=dict)
    # Button ordering in the frontend (lower first).
    sort_order = Column(Integer, nullable=False, default=0)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<OIDCProvider(id={self.id}, name='{self.name}', enabled={self.enabled})>"
