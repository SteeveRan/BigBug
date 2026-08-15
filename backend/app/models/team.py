"""
@file team.py
@description Team model — a shareable group of users with a single lead
             (owner). Teams own shared visibility for private resource
             providers (``visibility='team'`` + ``team_id``).
@dependencies app.database.Base, ./user.py, ./team_member.py
@relatedFiles ./team_member.py, ./resource_provider.py
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import relationship

from app.database import Base


class TeamRole(enum.StrEnum):
    lead = "lead"
    member = "member"


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    owner = relationship("User", foreign_keys=[owner_user_id])
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

    __table_args__ = (
        Index(
            "uq_teams_name",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
            sqlite_where=text("is_deleted = false"),
        ),
        Index("ix_teams_owner", "owner_user_id"),
    )

    def __repr__(self) -> str:
        return f"<Team(id={self.id}, name='{self.name}')>"
