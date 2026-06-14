"""
@file source_group.py
@description SourceGroup model — represents a group/organization within a source
             provider (e.g., GitHub org, GitLab group).
@dependencies app.database.Base, ./source_provider.py
@relatedFiles ./source_provider.py, ./source_repository.py, ./role_scope.py
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class SourceGroup(Base):
    __tablename__ = "source_groups"

    id = Column(Integer, primary_key=True, index=True)
    source_provider_id = Column(
        Integer,
        ForeignKey("source_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    external_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    full_path = Column(String(500), nullable=True)
    web_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    total_repos = Column(Integer, default=0, nullable=False)
    mirrored_repos = Column(Integer, default=0, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

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
    source_provider = relationship("SourceProvider", back_populates="source_groups")
    source_repositories = relationship(
        "SourceRepository", back_populates="source_group", cascade="all, delete-orphan"
    )
    role_scopes = relationship(
        "RoleScopeSourceGroup", back_populates="source_group", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SourceGroup(id={self.id}, name='{self.name}', external_id='{self.external_id}')>"
