"""
@file mirror_log.py
@description MirrorLog model — records each sync, freshness, import, or integrity
             check execution. Links to Mirror and optionally to PipelineRun.
@dependencies app.database.Base, ./mirror.py, ./pipeline_run.py
@relatedFiles ./mirror.py, ./pipeline_run.py
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import relationship

from app.database import Base


class MirrorLogType(enum.StrEnum):
    sync = "sync"
    freshness = "freshness"
    import_ = "import"
    integrity = "integrity"


class MirrorLog(Base):
    __tablename__ = "mirror_logs"

    id = Column(Integer, primary_key=True, index=True)
    mirror_id = Column(
        Integer,
        ForeignKey("mirrors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    log_type = Column(
        SAEnum(MirrorLogType, name="mirror_log_type_enum"),
        nullable=False,
    )
    pipeline_run_id = Column(
        Integer,
        ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    gitlab_pipeline_id = Column(String(255), nullable=True)
    gitlab_pipeline_url = Column(String(500), nullable=True)

    # 0=OK, 1=Failed, 2=Warning, 3=In Progress, 4=Pending
    status_flag = Column(Integer, nullable=False, default=4)
    status_text = Column(String(500), nullable=True)

    source_commit_sha = Column(String(40), nullable=True)
    source_commit_date = Column(DateTime(timezone=True), nullable=True)
    target_commit_sha = Column(String(40), nullable=True)
    commits_behind = Column(Integer, nullable=True)
    target_extra_commits = Column(Integer, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)

    triggered_by = Column(String(100), nullable=True)  # "scheduler" | "manual" | "webhook"
    details = Column(JSON, default=dict, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationships
    mirror = relationship("Mirror", back_populates="mirror_logs")
    pipeline_run = relationship("PipelineRun", back_populates="mirror_logs")

    def __repr__(self) -> str:
        return (
            f"<MirrorLog(id={self.id}, mirror_id={self.mirror_id}, "
            f"type='{self.log_type.value if self.log_type else None}')>"
        )
