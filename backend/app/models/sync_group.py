"""
@file sync_group.py
@description SyncGroup model — defines a logical grouping of mirrors that share
             the same pipeline, sync schedule, and freshness checking config.
@dependencies app.database.Base, ./pipeline.py
@relatedFiles ./mirror.py, ./role_scope.py
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SyncGroup(Base):
    __tablename__ = "sync_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    pipeline_id = Column(
        Integer,
        ForeignKey("pipelines.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_default = Column(Boolean, default=False, nullable=False)

    # Sync schedule
    sync_cron = Column(String(100), nullable=True)
    sync_enabled = Column(Boolean, default=True, nullable=False)
    sync_concurrency = Column(Integer, default=5, nullable=False)

    # Freshness check schedule
    freshness_cron = Column(String(100), nullable=True)
    freshness_enabled = Column(Boolean, default=True, nullable=False)
    freshness_concurrency = Column(Integer, default=5, nullable=False)

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
    pipeline = relationship("Pipeline", back_populates="sync_groups")
    mirrors = relationship(
        "Mirror", back_populates="sync_group", cascade="all, delete-orphan"
    )
    role_scopes = relationship(
        "RoleScopeSyncGroup", back_populates="sync_group", cascade="all, delete-orphan"
    )

    # Note: partial unique constraint on is_default=True will be enforced
    # via Alembic migration (postgresql_where).
    __table_args__ = (
        UniqueConstraint(
            "is_default",
            name="uq_sync_groups_default",
        ),
    )

    def __repr__(self) -> str:
        return f"<SyncGroup(id={self.id}, name='{self.name}', is_default={self.is_default})>"
