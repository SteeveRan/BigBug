"""
@file gitlab_component.py
@description GitLab Component model — represents a reusable GitLab CI/CD
             component registered in BigBug for use in pipeline templates.
@dependencies app.database.Base, ../models/gitlab_instance.py
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
    gitlab_instance_id = Column(Integer, ForeignKey("gitlab_instances.id"), nullable=False)
    project_path = Column(String(512), nullable=False)
    component_path = Column(String(512), nullable=False)
    version = Column(String(64), nullable=True)
    inputs_schema = Column(JSON, nullable=True)  # JSON Schema for component inputs
    is_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    gitlab_instance = relationship("GitlabInstance", lazy="select")

    def __repr__(self) -> str:
        return (
            f"<GitLabComponent(id={self.id}, name='{self.name}', "
            f"project='{self.project_path}', component='{self.component_path}')>"
        )
