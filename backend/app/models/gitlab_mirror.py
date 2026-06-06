from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class GitlabMirror(Base):
    __tablename__ = "gitlab_mirrors"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("github_projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # GitLab project info
    gitlab_project_id = Column(String(255), nullable=True, index=True)
    gitlab_namespace = Column(String(500), nullable=True)
    gitlab_url = Column(String(500), nullable=False)
    gitlab_name = Column(String(255), nullable=True)

    # Pipeline trigger
    pipeline_trigger_token = Column(String(255), nullable=True)
    mirrored_branch = Column(String(255), nullable=False, default="main")

    # Sync tracking
    last_synced_release_tag = Column(String(255), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)

    # Status
    # 0=ok, 1=failed, 2=warn/stale, 3=in_progress, 4=pending
    status_flag = Column(Integer, nullable=False, default=4)
    status_text = Column(String(500), nullable=True)

    # Import flag: True if mirror was imported from existing GitLab project
    is_imported = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    project = relationship("GithubProject", back_populates="mirrors")
    sync_schedules = relationship(
        "SyncSchedule", back_populates="mirror", cascade="all, delete-orphan"
    )
    sync_logs = relationship(
        "SyncLog", back_populates="mirror", cascade="all, delete-orphan"
    )
