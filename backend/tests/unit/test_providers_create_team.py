"""
@file test_providers_create_team.py
@description Unit tests for creating team-shared providers (stage 29).
@dependencies backend/app/services/providers/service.py, backend/tests/conftest.py
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ProviderVisibility,
)
from app.models.team import Team
from app.models.team_member import TeamMember
from app.models.user import User
from app.services.providers.service import ProviderService


def _user(user_id: int, permissions: list[str]) -> User:
    user = User(username=f"u{user_id}", email=f"u{user_id}@test.com")
    user.id = user_id
    user._cached_permissions = permissions
    return user


OWNER = ["providers:read", "providers:write", "providers:share"]


async def _team_with_member(db: AsyncSession, name: str, owner_id: int) -> int:
    team = Team(name=name, owner_user_id=owner_id)
    db.add(team)
    await db.flush()
    db.add(TeamMember(team_id=team.id, user_id=owner_id, role="lead"))
    await db.flush()
    return team.id


class TestCreateTeamProvider:
    async def test_create_team_provider_success(self, db_session: AsyncSession):
        team_id = await _team_with_member(db_session, "create-team", 7)
        svc = ProviderService(db_session)
        provider = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="team-create",
            label="Team create",
            user=_user(7, OWNER),
            visibility=ProviderVisibility.team,
            team_id=team_id,
        )
        assert provider.visibility == ProviderVisibility.team
        assert provider.team_id == team_id

    async def test_create_team_provider_without_membership_422(self, db_session: AsyncSession):
        # owner not a member of the team
        team = Team(name="no-membership", owner_user_id=99)
        db_session.add(team)
        await db_session.flush()

        svc = ProviderService(db_session)
        with pytest.raises(DomainError) as exc:
            await svc.create_provider(
                domain=ProviderDomain.git,
                subtype=ProviderSubtype.github,
                category=ProviderCategory.private,
                direction=ProviderDirection.external,
                name="no-membership",
                label="No membership",
                user=_user(7, OWNER),
                visibility=ProviderVisibility.team,
                team_id=team.id,
            )
        assert exc.value.status_code == 422

    async def test_team_visibility_without_team_id_integrity_error(self, db_session: AsyncSession):
        # Direct model-level CHECK enforcement (visibility=team without team_id).
        from app.models.resource_provider import ResourceProvider

        provider = ResourceProvider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="no-team-id",
            label="No team id",
            owner_user_id=7,
            visibility=ProviderVisibility.team,
            team_id=None,
        )
        db_session.add(provider)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()
