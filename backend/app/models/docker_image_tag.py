from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DockerImageTag(Base):
    """A specific tag of a Docker image from a registry source."""

    __tablename__ = "docker_image_tags"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(
        Integer,
        ForeignKey("docker_image_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Image identity
    image_name = Column(String(500), nullable=False, index=True)  # e.g., library/nginx
    tag = Column(String(255), nullable=False)  # e.g., 1.25-alpine

    # Image metadata (from registry API)
    digest = Column(String(255), nullable=True)  # SHA-256 digest
    size_bytes = Column(Integer, nullable=True)  # Compressed size
    architectures = Column(Text, nullable=True)  # JSON array of arch strings

    # Status
    # 0=ok (synced), 1=failed, 2=warning/stale, 3=in_progress, 4=pending (not synced)
    status_flag = Column(Integer, nullable=False, default=4)
    status_text = Column(String(500), nullable=True)

    # Sync tracking
    is_synced = Column(Boolean, default=False, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    source = relationship("DockerImageSource", back_populates="tags")
