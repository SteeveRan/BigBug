"""
@file mirror_release_log.py
@description MirrorReleaseLog model — records releases detected on the source
             repository for tracking purposes.
@dependencies app.database.Base, ./source_repository.py
@relatedFiles ./source_repository.py
"""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class MirrorReleaseLog(Base):
    __tablename__ = "mirror_release_logs"

    id = Column(Integer, primary_key=True, index=True)
    source_repository_id = Column(
        Integer,
        ForeignKey("source_repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    is_prerelease = Column(Boolean, default=False, nullable=False)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relationship
    source_repository = relationship("SourceRepository", back_populates="release_logs")

    def __repr__(self) -> str:
        return (
            f"<MirrorReleaseLog(id={self.id}, tag='{self.tag}', "
            f"repo_id={self.source_repository_id})>"
        )
