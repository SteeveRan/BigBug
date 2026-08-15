"""
@file test_providers_share.py
@description Unit tests for share/unshare (stage 28, section 12.3).
@dependencies backend/app/services/providers/service.py, backend/tests/conftest.py
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ProviderVisibility,
    ResourceProvider,
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


ADMIN = ["providers:read", "providers:write", "providers:read_all", "providers:share"]
OWNER = ["providers:read", "providers:write", "providers:share"]
NO_SHARE = ["providers:read", "providers:write"]


async def _provider(db: AsyncSession, name: str, owner_id: int) -> ResourceProvider:
    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.github,
        category=ProviderCategory.private,
        direction=ProviderDirection.external,
        name=name,
        label=name,
        owner_user_id=owner_id,
        visibility=ProviderVisibility.owner,
    )
    db.add(provider)
    await db.flush()
    return provider


async def _team(db: AsyncSession, name: str, owner_id: int) -> int:
    team = Team(name=name, owner_user_id=owner_id)
    db.add(team)
    await db.flush()
    db.add(TeamMember(team_id=team.id, user_id=owner_id, role="lead"))
    await db.flush()
    return team.id


class TestShare:
    async def test_share_success(self, db_session: AsyncSession):
        provider = await _provider(db_session, "share-1", 7)
        team_id = await _team(db_session, "team-share", 7)
        result = await ProviderService(db_session).share_provider(
            provider.id, team_id, _user(7, OWNER)
        )
        assert result.visibility == ProviderVisibility.team
        assert result.team_id == team_id

    async def test_share_non_owner_403(self, db_session: AsyncSession):
        provider = await _provider(db_session, "share-2", 7)
        team_id = await _team(db_session, "team-share2", 8)
        with pytest.raises(DomainError) as exc:
            await ProviderService(db_session).share_provider(provider.id, team_id, _user(8, OWNER))
        assert exc.value.status_code == 403

    async def test_share_non_member_422(self, db_session: AsyncSession):
        provider = await _provider(db_session, "share-3", 7)
        team_id = await _team(db_session, "team-share3", 9)
        with pytest.raises(DomainError) as exc:
            await ProviderService(db_session).share_provider(provider.id, team_id, _user(7, OWNER))
        assert exc.value.status_code == 422

    async def test_share_already_team_409(self, db_session: AsyncSession):
        provider = await _provider(db_session, "share-4", 7)
        team_id = await _team(db_session, "team-share4", 7)
        await ProviderService(db_session).share_provider(provider.id, team_id, _user(7, OWNER))
        with pytest.raises(DomainError) as exc:
            await ProviderService(db_session).share_provider(provider.id, team_id, _user(7, OWNER))
        assert exc.value.status_code == 409

    async def test_share_without_permission_403(self, db_session: AsyncSession):
        provider = await _provider(db_session, "share-5", 7)
        team_id = await _team(db_session, "team-share5", 7)
        with pytest.raises(DomainError) as exc:
            await ProviderService(db_session).share_provider(
                provider.id, team_id, _user(7, NO_SHARE)
            )
        assert exc.value.status_code == 403


class TestUnshare:
    async def test_unshare_success(self, db_session: AsyncSession):
        provider = await _provider(db_session, "unshare-1", 7)
        team_id = await _team(db_session, "team-unshare", 7)
        await ProviderService(db_session).share_provider(provider.id, team_id, _user(7, OWNER))
        result = await ProviderService(db_session).unshare_provider(provider.id, _user(7, OWNER))
        assert result.visibility == ProviderVisibility.owner
        assert result.team_id is None

    async def test_unshare_not_team_409(self, db_session: AsyncSession):
        provider = await _provider(db_session, "unshare-2", 7)
        with pytest.raises(DomainError) as exc:
            await ProviderService(db_session).unshare_provider(provider.id, _user(7, OWNER))
        assert exc.value.status_code == 409
