"""
@file test_team_service.py
@description Unit tests for TeamService (stage 25): lead membership invariant,
             atomic lead transfer, soft delete + unshare, member removal rules.
@dependencies backend/app/services/team.py, backend/tests/conftest.py
"""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.core.security import get_password_hash
from app.models.resource_provider import ProviderVisibility, ResourceProvider
from app.models.team import TeamRole
from app.models.team_member import TeamMember
from app.models.user import User
from app.services.team import TeamService


async def _user(db: AsyncSession, username: str, admin: bool = False) -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
    )
    if admin:
        user._cached_permissions = ["providers:read_all"]
    db.add(user)
    await db.flush()
    return user


async def _lead_member(db: AsyncSession, team_id: int) -> TeamMember | None:
    result = await db.execute(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.role == TeamRole.lead)
    )
    return result.scalar_one_or_none()


class TestCreateTeam:
    async def test_create_writes_lead_membership(self, db_session: AsyncSession):
        owner = await _user(db_session, "owner1")
        svc = TeamService(db_session)
        team = await svc.create_team("team-1", None, owner.id)

        lead = await _lead_member(db_session, team.id)
        assert lead is not None
        assert lead.user_id == owner.id

    async def test_duplicate_name_conflict(self, db_session: AsyncSession):
        owner = await _user(db_session, "owner-dup")
        svc = TeamService(db_session)
        await svc.create_team("dup-team", None, owner.id)
        with pytest.raises(DomainError) as exc:
            await svc.create_team("dup-team", None, owner.id)
        assert exc.value.status_code == 409


class TestTransferLead:
    async def test_update_owner_swaps_roles(self, db_session: AsyncSession):
        old = await _user(db_session, "old-lead")
        new = await _user(db_session, "new-lead")
        svc = TeamService(db_session)
        team = await svc.create_team("transfer", None, old.id)

        await svc.update_team(team.id, owner_user_id=new.id)

        old_member = await db_session.get(TeamMember, (team.id, old.id))
        new_member = await db_session.get(TeamMember, (team.id, new.id))
        assert old_member.role == TeamRole.member
        assert new_member.role == TeamRole.lead


class TestDeleteTeam:
    async def test_delete_unshares_providers(self, db_session: AsyncSession):
        owner = await _user(db_session, "owner-del")
        svc = TeamService(db_session)
        team = await svc.create_team("del-team", None, owner.id)

        provider = ResourceProvider(
            domain="git",
            subtype="github",
            category="private",
            direction="external",
            name="shared-provider",
            label="Shared",
            owner_user_id=owner.id,
            visibility=ProviderVisibility.team,
            team_id=team.id,
        )
        db_session.add(provider)
        await db_session.flush()

        await svc.delete_team(team.id)

        await db_session.refresh(provider)
        assert provider.visibility == ProviderVisibility.owner
        assert provider.team_id is None


class TestMembership:
    async def test_add_member_duplicate_409(self, db_session: AsyncSession):
        owner = await _user(db_session, "owner-mem")
        member = await _user(db_session, "member-mem")
        svc = TeamService(db_session)
        team = await svc.create_team("mem-team", None, owner.id)
        await svc.add_member(team.id, member.id)

        with pytest.raises(DomainError) as exc:
            await svc.add_member(team.id, member.id)
        assert exc.value.status_code == 409

    async def test_remove_lead_400(self, db_session: AsyncSession):
        owner = await _user(db_session, "owner-rm-lead")
        svc = TeamService(db_session)
        team = await svc.create_team("rm-lead", None, owner.id)

        with pytest.raises(DomainError) as exc:
            await svc.remove_member(team.id, owner.id, owner)
        assert exc.value.status_code == 400

    async def test_remove_member_unshares_their_providers(self, db_session: AsyncSession):
        owner = await _user(db_session, "owner-unshare")
        member = await _user(db_session, "member-unshare")
        svc = TeamService(db_session)
        team = await svc.create_team("unshare-team", None, owner.id)
        await svc.add_member(team.id, member.id)

        provider = ResourceProvider(
            domain="git",
            subtype="github",
            category="private",
            direction="external",
            name="member-provider",
            label="Member provider",
            owner_user_id=member.id,
            visibility=ProviderVisibility.team,
            team_id=team.id,
        )
        db_session.add(provider)
        await db_session.flush()

        await svc.remove_member(team.id, member.id, owner)

        await db_session.refresh(provider)
        assert provider.visibility == ProviderVisibility.owner
        assert provider.team_id is None

    async def test_self_exit_allowed(self, db_session: AsyncSession):
        owner = await _user(db_session, "owner-self")
        member = await _user(db_session, "member-self")
        svc = TeamService(db_session)
        team = await svc.create_team("self-team", None, owner.id)
        await svc.add_member(team.id, member.id)

        await svc.remove_member(team.id, member.id, member)
        assert await db_session.get(TeamMember, (team.id, member.id)) is None
