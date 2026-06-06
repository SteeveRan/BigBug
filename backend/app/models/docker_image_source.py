from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DockerImageSource(Base):
    """Docker registry source for tracking and syncing container images.

    Represents an external Docker registry (Docker Hub, Harbor, etc.) from
    which images and their tags are tracked and synced.
    """

    __tablename__ = "docker_image_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    registry_url = Column(
        String(500), nullable=False
    )  # e.g., https://registry-1.docker.io
    description = Column(Text, nullable=True)

    # GitLab mirror project for Docker sync pipelines
    gitlab_project_id = Column(String(255), nullable=True)
    gitlab_project_url = Column(String(500), nullable=True)

    # Sync tracking
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    # 0=ok, 1=failed, 2=warn/stale, 3=in_progress, 4=pending
    status_flag = Column(Integer, nullable=False, default=4)
    status_text = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    tags = relationship(
        "DockerImageTag", back_populates="source", cascade="all, delete-orphan"
    )
    sync_logs = relationship(
        "DockerSyncLog", back_populates="source", cascade="all, delete-orphan"
    )
