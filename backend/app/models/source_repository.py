"""
@file source_repository.py
@description SourceRepository model — represents a single repository discovered within
             a source group (GitHub repo, GitLab project).
@dependencies app.database.Base, ./source_group.py, ./source_provider.py
@relatedFiles ./source_group.py, ./source_provider.py, ./mirror.py, ./mirror_release_log.py
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from app.database import Base


class DiscoveryStatus(enum.StrEnum):
    new = "new"
    existing = "existing"
    removed = "removed"


class SourceRepository(Base):
    __tablename__ = "source_repositories"

    id = Column(Integer, primary_key=True, index=True)
    source_group_id = Column(
        Integer,
        ForeignKey("source_groups.id", ondelete="CASCADE"),
        nullable=True,
    )
    # Providers V3 (phase 7E): git source is a resource_providers row
    # (domain=git, direction=external). Legacy source_provider_id removed.
    provider_id = Column(
        Integer,
        ForeignKey("resource_providers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_id = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    full_name = Column(String(500), nullable=False)
    web_url = Column(String(500), nullable=True)
    clone_url_https = Column(String(500), nullable=True)
    clone_url_ssh = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    language = Column(String(100), nullable=True)
    stars_count = Column(Integer, default=0, nullable=False)
    forks_count = Column(Integer, default=0, nullable=False)
    is_private = Column(Boolean, default=False, nullable=False)
    default_branch = Column(String(255), nullable=True)
    license_spdx = Column(String(100), nullable=True)
    license_name = Column(String(255), nullable=True)
    readme_html = Column(Text, nullable=True)
    readme_fetched_at = Column(DateTime(timezone=True), nullable=True)
    latest_release_tag = Column(String(255), nullable=True)
    latest_release_name = Column(String(255), nullable=True)
    latest_release_date = Column(DateTime(timezone=True), nullable=True)
    latest_release_url = Column(String(500), nullable=True)
    latest_prerelease_tag = Column(String(255), nullable=True)
    latest_prerelease_name = Column(String(255), nullable=True)
    latest_prerelease_date = Column(DateTime(timezone=True), nullable=True)
    latest_prerelease_url = Column(String(500), nullable=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    is_fork = Column(Boolean, default=False, nullable=False)
    is_disabled = Column(Boolean, default=False, nullable=False)
    discovery_status = Column(
        SAEnum(DiscoveryStatus, name="discovery_status_enum"),
        default=DiscoveryStatus.new,
        nullable=False,
    )
    discovered_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    source_created_at = Column(DateTime(timezone=True), nullable=True)
    source_updated_at = Column(DateTime(timezone=True), nullable=True)
    source_pushed_at = Column(DateTime(timezone=True), nullable=True)

    # Status tracking for async metadata fetch
    status_flag = Column(Integer, default=4, nullable=False)
    status_text = Column(String(500), nullable=True)
    last_commit_sha = Column(String(40), nullable=True)
    last_commit_date = Column(DateTime(timezone=True), nullable=True)
    last_commit_author = Column(String(255), nullable=True)
    last_commit_message = Column(Text, nullable=True)

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
    source_group = relationship("SourceGroup", back_populates="source_repositories")
    provider = relationship("ResourceProvider", foreign_keys=[provider_id])
    mirrors = relationship(
        "Mirror", back_populates="source_repository", cascade="all, delete-orphan"
    )
    release_logs = relationship(
        "MirrorReleaseLog", back_populates="source_repository", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<SourceRepository(id={self.id}, full_name='{self.full_name}')>"
