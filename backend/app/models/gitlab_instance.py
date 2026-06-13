"""
@file gitlab_instance.py
@description GitLab instance model — stores connection details for multiple
             GitLab instances. The access token is encrypted at rest via Fernet.
@dependencies app.database.Base, app.core.secrets (via service layer)
@relatedFiles ./harbor_instance.py, ./github_instance.py, ../../schemas/integrations.py
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class GitlabInstance(Base):
    __tablename__ = "gitlab_instances"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    url = Column(String(512), nullable=False)
    token = Column(Text, nullable=True)  # Fernet-encrypted at rest
    is_active = Column(Boolean, default=True, nullable=False)
    verify_ssl = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    default_group_id = Column(Integer, nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    status_flag = Column(
        Integer, default=0, nullable=False
    )  # 0=OK,1=Failed,2=Warning,3=In Progress,4=Pending
    status_text = Column(String(255), default="OK", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    pipelines = relationship("Pipeline", back_populates="gitlab_instance")

    def __repr__(self) -> str:
        return f"<GitlabInstance(id={self.id}, name='{self.name}', url='{self.url}')>"
