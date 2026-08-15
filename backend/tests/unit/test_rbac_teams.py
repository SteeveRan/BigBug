"""
@file test_rbac_teams.py
@description Unit tests for team scope in RBACService (stage 26): team_ids in
             effective scope, check_scope_access for teams, is_team_lead.
@dependencies backend/app/services/rbac_service.py, backend/tests/conftest.py
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash
from app.models.role import Role, UserRole
from app.models.team import Team, TeamRole
from app.models.team_member import TeamMember
from app.models.user import User
from app.services.rbac_service import RBACService


async def _user_with_role(db: AsyncSession, username: str, role_name: str | None) -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    if role_name is not None:
        result = await db.execute(select(Role).where(Role.name == role_name))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=role_name, description=role_name)
            db.add(role)
            await db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))

    await db.commit()
    await db.refresh(user)
    return user


class TestTeamScope:
    async def test_team_ids_reflect_membership(self, db_session: AsyncSession):
        user = await _user_with_role(db_session, "team-scope-user", "operator")
        t = Team(name="scope-team", owner_user_id=user.id)
        db_session.add(t)
        await db_session.flush()
        db_session.add(TeamMember(team_id=t.id, user_id=user.id, role=TeamRole.member))
        await db_session.commit()

        scope = await RBACService(db_session).get_user_effective_scope(user.id)
        assert t.id in scope["team_ids"]

    async def test_admin_team_ids_none(self, db_session: AsyncSession):
        user = await _user_with_role(db_session, "team-admin-user", "admin")
        scope = await RBACService(db_session).get_user_effective_scope(user.id)
        assert scope["team_ids"] is None

    async def test_check_scope_access_team(self, db_session: AsyncSession):
        user = await _user_with_role(db_session, "team-access-user", "operator")
        t = Team(name="access-team", owner_user_id=user.id)
        db_session.add(t)
        await db_session.flush()
        db_session.add(TeamMember(team_id=t.id, user_id=user.id, role=TeamRole.lead))
        await db_session.commit()

        rbac = RBACService(db_session)
        assert await rbac.check_scope_access(user.id, "team", t.id) is True
        assert await rbac.check_scope_access(user.id, "team", t.id + 999) is False

    async def test_is_team_lead(self, db_session: AsyncSession):
        lead = await _user_with_role(db_session, "lead-user", "operator")
        member = await _user_with_role(db_session, "member-user", "operator")
        t = Team(name="lead-team", owner_user_id=lead.id)
        db_session.add(t)
        await db_session.flush()
        db_session.add(TeamMember(team_id=t.id, user_id=lead.id, role=TeamRole.lead))
        db_session.add(TeamMember(team_id=t.id, user_id=member.id, role=TeamRole.member))
        await db_session.commit()

        rbac = RBACService(db_session)
        assert await rbac.is_team_lead(lead.id, t.id) is True
        assert await rbac.is_team_lead(member.id, t.id) is False
