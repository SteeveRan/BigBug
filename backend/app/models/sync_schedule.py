from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class SyncSchedule(Base):
    __tablename__ = "sync_schedules"

    id = Column(Integer, primary_key=True, index=True)
    mirror_id = Column(
        Integer, ForeignKey("gitlab_mirrors.id", ondelete="CASCADE"), nullable=False, index=True
    )

    cron_expression = Column(String(100), nullable=True)
    is_enabled = Column(Boolean, default=True, nullable=False)
    use_default_schedule = Column(Boolean, default=True, nullable=False)

    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    mirror = relationship("GitlabMirror", back_populates="sync_schedules")
