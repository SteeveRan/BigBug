"""
@file oidc_config.py
@description OIDC / SSO configuration model — stores the dynamic OIDC provider
             settings previously hardcoded in environment variables. A single-row
             table (singleton pattern); the client_secret is encrypted at rest
             via Fernet.
@dependencies app.database.Base, app.core.secrets (via service layer)
@relatedFiles ./gitlab_instance.py (model pattern), ../../services/oidc_config.py
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON

from app.database import Base


class OIDCConfig(Base):
    __tablename__ = "oidc_config"

    id = Column(Integer, primary_key=True, index=True)
    issuer_url = Column(String(512), nullable=False, default="")
    client_id = Column(String(255), nullable=False, default="")
    client_secret = Column(Text, nullable=True)  # Fernet-encrypted at rest
    frontend_client_id = Column(String(255), nullable=False, default="")
    enabled = Column(Boolean, default=False, nullable=False)
    public_url = Column(String(512), nullable=True)
    role_mapping = Column(JSON, nullable=False, default=dict)

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
        return f"<OIDCConfig(id={self.id}, issuer='{self.issuer_url}', enabled={self.enabled})>"
