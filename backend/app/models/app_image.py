from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class AppImage(Base):
    __tablename__ = "app_images"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer,
        ForeignKey("github_projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gold_image_id = Column(
        Integer,
        ForeignKey("gold_images.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name = Column(String(255), nullable=False, index=True)
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
    project = relationship("GithubProject", back_populates="app_images")
    gold_image = relationship("GoldImage", back_populates="app_images")
    versions = relationship(
        "ImageVersion",
        primaryjoin="and_(ImageVersion.app_image_id == AppImage.id, "
        "ImageVersion.image_type == 'app')",
        back_populates="app_image",
        cascade="all, delete-orphan",
    )
    build_schedules = relationship(
        "BuildSchedule",
        primaryjoin="and_(BuildSchedule.app_image_id == AppImage.id, "
        "BuildSchedule.image_type == 'app')",
        back_populates="app_image",
        cascade="all, delete-orphan",
    )
