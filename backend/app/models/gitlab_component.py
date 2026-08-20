"""
@file gitlab_component.py
@description GitLab Component model — represents a reusable GitLab CI/CD
             component registered in BigBug for use in pipeline templates.
@dependencies app.database.Base, ../models/resource_provider.py
@relatedFiles ../../schemas/pipeline.py, ../../services/pipeline.py
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class GitLabComponent(Base):
    __tablename__ = "gitlab_components"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True)
    # Providers V3 (phase 7A): the component runs against the platform GitLab,
    # a resource_providers row with subtype=gitlab, category=system,
    # direction=internal. The legacy gitlab_instance_id column is removed.
    provider_id = Column(
        Integer,
        ForeignKey("resource_providers.id", ondelete="SET NULL"),
        nullable=False,
        index=True,
    )
    project_path = Column(String(512), nullable=False)
    component_path = Column(String(512), nullable=False)
    version = Column(String(64), nullable=True)
    inputs_schema = Column(JSON, nullable=True)  # JSON Schema for component inputs
    gitlab_project_id = Column(
        Integer,
        ForeignKey("gitlab_projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    provider = relationship("ResourceProvider", foreign_keys=[provider_id])
    gitlab_project = relationship("GitlabProject", back_populates="components")
    pipeline_components = relationship(
        "PipelineComponent", back_populates="component", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<GitLabComponent(id={self.id}, name='{self.name}', "
            f"project='{self.project_path}', component='{self.component_path}')>"
        )
