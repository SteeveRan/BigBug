"""
@file credential.py
@description Credential model — stores encrypted secrets (tokens, keys, passwords)
             for authenticating with source providers (GitHub, GitLab, etc.).
@dependencies app.database.Base, app.core.secrets (via service layer)
@relatedFiles ./source_provider.py, ./role_scope.py
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class CredentialType(str, enum.Enum):
    github_token = "github_token"
    gitlab_token = "gitlab_token"
    https_basic = "https_basic"
    ssh_key = "ssh_key"


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    credential_type = Column(
        SAEnum(CredentialType, name="credential_type_enum"),
        nullable=False,
    )
    provider = Column(String(50), nullable=False)  # "github", "gitlab", "generic"
    username = Column(String(255), nullable=True)
    encrypted_secret = Column(Text, nullable=True)
    ssh_public_key = Column(Text, nullable=True)
    base_url = Column(String(500), nullable=True)

    # 0=OK, 1=Failed, 2=Warning, 3=In Progress, 4=Pending
    status_flag = Column(Integer, nullable=False, default=0)
    status_text = Column(String(500), nullable=True)
    last_tested_at = Column(DateTime(timezone=True), nullable=True)

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    source_providers = relationship(
        "SourceProvider", back_populates="credential", cascade="all, delete-orphan"
    )
    role_scopes = relationship(
        "RoleScopeCredential", back_populates="credential", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Credential(id={self.id}, name='{self.name}', "
            f"type='{self.credential_type.value if self.credential_type else None}')>"
        )
