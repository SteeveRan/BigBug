from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class GithubProject(Base):
    __tablename__ = "github_projects"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(Integer, ForeignKey("github_orgs.id", ondelete="CASCADE"), nullable=False)

    # GitHub metadata
    github_id = Column(Integer, nullable=True, unique=True)
    name = Column(String(255), nullable=False)
    full_name = Column(String(512), nullable=False, unique=True, index=True)
    github_url = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    custom_description = Column(Text, nullable=True)  # editable by operator
    readme_md = Column(Text, nullable=True)
    default_branch = Column(String(255), nullable=False, default="main")
    homepage_url = Column(String(500), nullable=True)

    # License
    license_spdx = Column(String(100), nullable=True)   # e.g. "MIT", "Apache-2.0"
    license_name = Column(String(255), nullable=True)   # full name
    license_text = Column(Text, nullable=True)

    # Flags
    is_archived = Column(Boolean, default=False, nullable=False)
    is_fork = Column(Boolean, default=False, nullable=False)

    # Stale tracking
    stale_threshold_days = Column(Integer, nullable=False, default=30)
    is_stale = Column(Boolean, default=False, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    # GitHub timestamps
    github_created_at = Column(DateTime(timezone=True), nullable=True)
    github_updated_at = Column(DateTime(timezone=True), nullable=True)
    github_pushed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    org = relationship("GithubOrg", back_populates="projects")
    releases = relationship("GithubRelease", back_populates="project", cascade="all, delete-orphan")
    mirrors = relationship("GitlabMirror", back_populates="project", cascade="all, delete-orphan")
    app_images = relationship("AppImage", back_populates="project")
