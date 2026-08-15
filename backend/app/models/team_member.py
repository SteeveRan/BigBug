"""
@file team_member.py
@description TeamMember association model — membership row in a team. The lead's
             membership is duplicated as a row with ``role='lead'`` (invariant
             enforced by TeamService) so a single JOIN covers team visibility.
@dependencies app.database.Base, ./team.py, ./user.py
@relatedFiles ./team.py, ../services/team.py
"""

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.team import TeamRole


class TeamMember(Base):
    __tablename__ = "team_members"

    team_id = Column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role = Column(
        SAEnum(TeamRole, name="team_role_enum"),
        nullable=False,
        default=TeamRole.member,
    )
    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships
    team = relationship("Team", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (Index("ix_team_members_user", "user_id"),)

    def __repr__(self) -> str:
        return f"<TeamMember(team_id={self.team_id}, user_id={self.user_id}, role='{self.role}')>"
