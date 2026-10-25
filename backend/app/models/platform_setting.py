"""
@file platform_setting.py
@description Generic key/value platform setting (issue #114): first consumer is
              the maintenance_mode flag that stops scheduler enqueue passes.
              Deliberately NOT a settings framework — one row per flag.
@dependencies app.database.Base
@relatedFiles ../../services/platform_settings.py, ../../api/maintenance.py
"""

from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String

from app.database import Base


class PlatformSetting(Base):
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), nullable=False, unique=True)
    # JSON value — callers own the shape (maintenance_mode stores a bool).
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<PlatformSetting(key='{self.key}', value={self.value!r})>"
