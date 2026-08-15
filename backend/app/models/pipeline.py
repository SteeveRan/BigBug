"""
@file pipeline.py
@description Pipeline and PipelineComponent models — Pipelines are reusable
             CI/CD workflow definitions composed of GitLab Components. A Pipeline
             can be marked as default and is assigned to SyncGroups.
@dependencies app.database.Base, ./gitlab_component.py
@relatedFiles ./sync_group.py, ./pipeline_run.py
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Pipeline(Base):
    __tablename__ = "pipelines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    # Providers V3 (phase 7A): the platform GitLab is a resource_providers row
    # with subtype=gitlab, category=system, direction=internal (11.3.4).
    # The legacy gitlab_instance_id column is removed.
    provider_id = Column(
        Integer,
        ForeignKey("resource_providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ref = Column(String(255), nullable=False)
    default_variables = Column(JSON, default=dict, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    provider = relationship("ResourceProvider", foreign_keys=[provider_id])
    components = relationship(
        "PipelineComponent", back_populates="pipeline", cascade="all, delete-orphan"
    )
    pipeline_runs = relationship(
        "PipelineRun", back_populates="pipeline", cascade="all, delete-orphan"
    )
    sync_groups = relationship("SyncGroup", back_populates="pipeline", cascade="all, delete-orphan")

    # Note: partial unique constraint on is_default=True is enforced
    # via Alembic migration (postgresql_where) for PostgreSQL.
    # Application logic (PipelineService) handles the constraint in all backends.
    __table_args__: tuple = ()

    def __repr__(self) -> str:
        return f"<Pipeline(id={self.id}, name='{self.name}', is_default={self.is_default})>"


class PipelineComponent(Base):
    __tablename__ = "pipeline_components"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(
        Integer,
        ForeignKey("pipelines.id", ondelete="CASCADE"),
        nullable=False,
    )
    component_id = Column(
        Integer,
        ForeignKey("gitlab_components.id", ondelete="RESTRICT"),
        nullable=False,
    )
    order = Column(Integer, default=0, nullable=False)
    overrides = Column(JSON, default=dict, nullable=False)

    # Relationships
    pipeline = relationship("Pipeline", back_populates="components")
    component = relationship("GitLabComponent", back_populates="pipeline_components")

    def __repr__(self) -> str:
        return (
            f"<PipelineComponent(id={self.id}, pipeline_id={self.pipeline_id}, "
            f"component_id={self.component_id}, order={self.order})>"
        )
