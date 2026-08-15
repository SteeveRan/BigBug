"""
@file test_team_model.py
@description Unit tests for Team / TeamMember models (stage 23): defaults,
             timestamps, PK(team_id, user_id), repr, TeamRole enum values.
@dependencies backend/app/models/team.py, backend/app/models/team_member.py
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.team import Team, TeamRole
from app.models.team_member import TeamMember


class TestTeamRole:
    def test_values(self):
        assert {r.value for r in TeamRole} == {"lead", "member"}


class TestTeamModel:
    async def test_creation_minimal(self, db_session: AsyncSession):
        team = Team(name="platform", owner_user_id=1)
        db_session.add(team)
        await db_session.flush()
        assert team.id is not None
        assert team.is_deleted is False

    async def test_soft_delete_fields(self, db_session: AsyncSession):
        team = Team(name="soft", owner_user_id=1)
        db_session.add(team)
        await db_session.flush()
        team.is_deleted = True
        team.deleted_at = datetime.now()
        await db_session.flush()
        assert team.is_deleted is True
        assert team.deleted_at is not None

    def test_repr(self):
        team = Team(id=3, name="repro")
        assert "repro" in repr(team)


class TestTeamMemberModel:
    async def test_composite_pk(self, db_session: AsyncSession):
        team = Team(name="team-pk", owner_user_id=1)
        db_session.add(team)
        await db_session.flush()
        member = TeamMember(team_id=team.id, user_id=1, role=TeamRole.lead)
        db_session.add(member)
        await db_session.flush()
        assert member.team_id == team.id
        assert member.user_id == 1
        assert member.role == TeamRole.lead

    def test_repr(self):
        member = TeamMember(team_id=1, user_id=2, role=TeamRole.member)
        assert "team_id=1" in repr(member)
        assert "member" in repr(member)
