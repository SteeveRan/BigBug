"""
@file sync_run.py
@description Sync-run tracking row (issue #112, ADR-0039 Phase 4): one row per
             tracked task execution — the operational index the admin console
             reads (DB-as-DLQ: the DLQ is a ``failed_permanent`` filter).
             Written by task wrappers (app/tasks/run_tracking.py), not by
             business services; log tables stay as detailed records.
@dependencies app.database.Base
@relatedFiles ../../tasks/run_tracking.py, ../../api/sync_runs.py, ../../schemas/sync_run.py
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text

from app.database import Base


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(200), nullable=False)
    entity_type = Column(String(100), nullable=True)
    entity_id = Column(Integer, nullable=True)
    # queued | running | succeeded | failed | failed_permanent | superseded
    # ("superseded" marks the old row of a stuck run that was requeued).
    status = Column(String(50), nullable=False, default="running")
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    # Original task arguments — retry/requeue re-enqueues via the standard
    # enqueue path with these.
    payload = Column(JSON, nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("ix_sync_runs_task_entity", "task_name", "entity_type", "entity_id"),
        Index(
            "ix_sync_runs_active",
            "status",
            postgresql_where=sa.text("status IN ('queued', 'running')"),
            sqlite_where=sa.text("status IN ('queued', 'running')"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<SyncRun(id={self.id}, task='{self.task_name}', "
            f"status='{self.status}', attempts={self.attempts})>"
        )
