"""
@file notification_outbox.py
@description NotificationOutbox model — transactional outbox row (ADR-0039
             Phase 3): written in the SAME DB transaction as the sync commit,
             consumed later by send_pending_outbox_task. The unique dedup_key
             makes redelivery a no-op.
@dependencies app.database.Base
@relatedFiles ../services/sync_engine.py, ../tasks/outbox_tasks.py
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Index, Integer, String

from app.database import Base


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id = Column(Integer, primary_key=True, index=True)
    # Unique: insert-or-skip on this key prevents duplicate notifications
    # across crash-restarts and task redelivery.
    dedup_key = Column(String(500), nullable=False, unique=True, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    sent_at = Column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<NotificationOutbox(id={self.id}, event_type='{self.event_type}', "
            f"sent_at={self.sent_at})>"
        )


# Fast unsent-scan for the sender (partial index on Postgres).
Index(
    "ix_notification_outbox_unsent",
    NotificationOutbox.created_at,
    postgresql_where=NotificationOutbox.sent_at.is_(None),
)
