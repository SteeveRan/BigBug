from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class BuildSchedule(Base):
    __tablename__ = "build_schedules"

    id = Column(Integer, primary_key=True, index=True)

    # Discriminator: "gold" or "app"
    image_type = Column(String(10), nullable=False, index=True)

    # FK to parent image — one of these is set, the other is NULL
    gold_image_id = Column(
        Integer, ForeignKey("gold_images.id", ondelete="CASCADE"), nullable=True, index=True
    )
    app_image_id = Column(
        Integer, ForeignKey("app_images.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Schedule config
    # Priority: is_enabled=False → no runs
    #           use_default_schedule=True → use system default cron
    #           else → use cron_expression
    is_enabled = Column(Boolean, default=True, nullable=False)
    use_default_schedule = Column(Boolean, default=True, nullable=False)
    cron_expression = Column(String(100), nullable=True)

    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    gold_image = relationship(
        "GoldImage",
        primaryjoin="and_(BuildSchedule.gold_image_id == GoldImage.id, "
                    "BuildSchedule.image_type == 'gold')",
        back_populates="build_schedules",
        foreign_keys=[gold_image_id],
    )
    app_image = relationship(
        "AppImage",
        primaryjoin="and_(BuildSchedule.app_image_id == AppImage.id, "
                    "BuildSchedule.image_type == 'app')",
        back_populates="build_schedules",
        foreign_keys=[app_image_id],
    )
