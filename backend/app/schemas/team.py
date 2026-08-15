"""
@file team.py
@description Pydantic schemas for the teams API (12.3). TeamOut is built from
             service-layer data (owner username, member count, caller's role)
             rather than directly from ORM attributes.
@dependencies pydantic
@relatedFiles ../models/team.py, ../models/team_member.py, ../services/team.py
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.team import TeamRole


class TeamCreate(BaseModel):
    """Payload to create a team (admin only)."""

    name: str = Field(..., max_length=255)
    description: str | None = None
    owner_user_id: int


class TeamUpdate(BaseModel):
    """Partial team update (admin only)."""

    name: str | None = Field(None, max_length=255)
    description: str | None = None
    owner_user_id: int | None = None


class TeamOwnerOut(BaseModel):
    """Compact owner reference."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class TeamOut(BaseModel):
    """Public team representation (12.3)."""

    id: int
    name: str
    description: str | None = None
    owner: TeamOwnerOut
    members_count: int
    my_role: TeamRole | None = None


class TeamMemberAdd(BaseModel):
    """Invite a user by id (12.3)."""

    user_id: int


class TeamMemberOut(BaseModel):
    """A team member (12.3)."""

    user_id: int
    username: str
    role: TeamRole
    joined_at: datetime
