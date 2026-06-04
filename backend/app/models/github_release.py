from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


class GithubRelease(Base):
    __tablename__ = "github_releases"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(
        Integer, ForeignKey("github_projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    github_release_id = Column(Integer, nullable=True, unique=True)
    tag_name = Column(String(255), nullable=False)
    name = Column(String(500), nullable=True)
    body = Column(Text, nullable=True)
    is_prerelease = Column(Boolean, default=False, nullable=False)
    is_draft = Column(Boolean, default=False, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    project = relationship("GithubProject", back_populates="releases")
