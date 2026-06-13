"""
@file mirror.py
@description Mirror model — represents a git mirror of a source repository into
             GitLab. Does NOT hold direct FK to GitlabInstance/Components; instead
             reaches them through SyncGroup → Pipeline → GitlabInstance.
@dependencies app.database.Base, ./source_repository.py, ./sync_group.py
@relatedFiles ./source_repository.py, ./sync_group.py, ./mirror_log.py
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Mirror(Base):
    __tablename__ = "mirrors"

    # Mapper configuration to disable confirm_deleted_rows warning
    __mapper_args__ = {
        "confirm_deleted_rows": False
    }

    id = Column(Integer, primary_key=True, index=True)
    source_repository_id = Column(
        Integer,
        ForeignKey("source_repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    sync_group_id = Column(
        Integer,
        ForeignKey("sync_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_namespace = Column(String(500), nullable=True)
    target_project_name = Column(String(255), nullable=True)
    target_project_id = Column(String(255), nullable=True)
    target_web_url = Column(String(500), nullable=True)

    # 0=OK, 1=Failed, 2=Warning, 3=In Progress, 4=Pending
    status_flag = Column(Integer, nullable=False, default=4)
    status_text = Column(String(500), nullable=True)
    last_sync_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String(50), nullable=True)
    last_freshness_check_at = Column(DateTime(timezone=True), nullable=True)
    last_freshness_status = Column(String(50), nullable=True)
    last_known_commit_sha = Column(String(40), nullable=True)
    last_known_commit_date = Column(DateTime(timezone=True), nullable=True)
    last_known_commit_author = Column(String(255), nullable=True)
    target_diverged_commits = Column(Integer, default=0, nullable=False)

    # Import flag: True if mirror was imported from existing GitLab project
    is_imported = Column(Boolean, default=False, nullable=False)

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
    source_repository = relationship("SourceRepository", back_populates="mirrors")
    sync_group = relationship("SyncGroup", back_populates="mirrors")
    mirror_logs = relationship("MirrorLog", back_populates="mirror", cascade="all, delete-orphan")

    @property
    def pipeline(self):
        """Return the Pipeline via SyncGroup, or None."""
        if self.sync_group is not None:
            return self.sync_group.pipeline
        return None

    @property
    def target_gitlab_instance(self):
        """Return the GitlabInstance via SyncGroup → Pipeline, or None."""
        pl = self.pipeline
        if pl is not None:
            return pl.gitlab_instance
        return None

    def __repr__(self) -> str:
        return (
            f"<Mirror(id={self.id}, src_repo={self.source_repository_id}, "
            f"target='{self.target_project_name}')>"
        )
