from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class GithubOrg(Base):
    __tablename__ = "github_orgs"

    id = Column(Integer, primary_key=True, index=True)
    login = Column(String(255), unique=True, nullable=False, index=True)
    # "Organization" or "User"
    type = Column(String(50), nullable=False, default="Organization")
    avatar_url = Column(String(500), nullable=True)
    github_id = Column(Integer, nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    projects = relationship("GithubProject", back_populates="org", cascade="all, delete-orphan")
