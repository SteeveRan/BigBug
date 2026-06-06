from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class GoldImage(Base):
    __tablename__ = "gold_images"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    os_family = Column(String(100), nullable=False)  # e.g. "ubuntu", "alpine", "debian"
    description = Column(Text, nullable=True)
    dockerfile = Column(Text, nullable=True)
    gitlab_project_id = Column(String(255), nullable=True)
    gitlab_project_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    app_images = relationship("AppImage", back_populates="gold_image")
    versions = relationship(
        "ImageVersion",
        primaryjoin="and_(ImageVersion.gold_image_id == GoldImage.id, "
        "ImageVersion.image_type == 'gold')",
        back_populates="gold_image",
        cascade="all, delete-orphan",
    )
    build_schedules = relationship(
        "BuildSchedule",
        primaryjoin="and_(BuildSchedule.gold_image_id == GoldImage.id, "
        "BuildSchedule.image_type == 'gold')",
        back_populates="gold_image",
        cascade="all, delete-orphan",
    )
