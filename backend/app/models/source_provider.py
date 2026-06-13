"""
@file source_provider.py
@description SourceProvider model — represents a configured source hosting platform
             (GitHub, GitLab, Bitbucket) optionally authenticated via a Credential.
@dependencies app.database.Base, ./credential.py
@relatedFiles ./credential.py, ./source_group.py, ./role_scope.py
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.database import Base


class ProviderType(enum.StrEnum):
    github = "github"
    gitlab = "gitlab"
    bitbucket = "bitbucket"
    generic = "generic"


class SourceProvider(Base):
    __tablename__ = "source_providers"

    id = Column(Integer, primary_key=True, index=True)
    credential_id = Column(
        Integer,
        ForeignKey("credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_type = Column(
        SAEnum(ProviderType, name="provider_type_enum"),
        nullable=False,
    )
    label = Column(String(255), nullable=False)

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
    credential = relationship("Credential", back_populates="source_providers")
    source_groups = relationship(
        "SourceGroup", back_populates="source_provider", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<SourceProvider(id={self.id}, label='{self.label}', "
            f"type='{self.provider_type.value if self.provider_type else None}')>"
        )
