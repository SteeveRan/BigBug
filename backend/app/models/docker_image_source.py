from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DockerImageSource(Base):
    """Docker registry source for tracking and syncing container images.

    Represents an external Docker registry (Docker Hub, Harbor, etc.) from
    which images and their tags are tracked and synced.

    Links back to the configured DockerRegistryInstance that provides credentials
    and connection details for the source registry.
    """

    __tablename__ = "docker_image_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    registry_url = Column(String(500), nullable=False)  # e.g., https://registry-1.docker.io
    description = Column(Text, nullable=True)

    # Link to the configured registry instance that provides credentials
    registry_instance_id = Column(
        Integer,
        ForeignKey("docker_registry_instances.id", ondelete="SET NULL"),
        nullable=True,
        comment="Configured registry instance used as source for this image",
    )

    # GitLab mirror project for Docker sync pipelines
    gitlab_project_id = Column(String(255), nullable=True)
    gitlab_project_url = Column(String(500), nullable=True)

    # Target registry for mirroring (where images are copied to)
    target_registry_url = Column(String(500), nullable=True)
    target_project = Column(String(255), nullable=True)

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
    tags = relationship("DockerImageTag", back_populates="source", cascade="all, delete-orphan")
    sync_logs = relationship("DockerSyncLog", back_populates="source", cascade="all, delete-orphan")
    sync_schedules = relationship(
        "SyncSchedule", back_populates="docker_image_source", cascade="all, delete-orphan"
    )
    registry_instance = relationship(
        "DockerRegistryInstance",
        foreign_keys=[registry_instance_id],
        lazy="selectin",
    )
