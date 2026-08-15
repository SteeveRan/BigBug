"""
@file test_providers_visibility.py
@description Unit tests for the visibility matrix (stage 27, section 12.2.1):
             owner sees own, member sees team-shared, outsider does not,
             public private visible to all, system hidden from regular users.
@dependencies backend/app/services/providers/service.py, backend/tests/conftest.py
"""

from sqlalchemy.ext.asyncio import AsyncSession

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


ADMIN = ["providers:read", "providers:write", "providers:read_all", "providers_system:write"]
OPERATOR = ["providers:read", "providers:write", "providers:use"]


async def _provider(
    db: AsyncSession,
    *,
    name: str,
    category: ProviderCategory,
    owner_user_id: int | None,
    visibility: ProviderVisibility,
    team_id: int | None = None,
) -> ResourceProvider:
    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.github,
        category=category,
        direction=ProviderDirection.external,
        name=name,
        label=name,
        owner_user_id=owner_user_id,
        visibility=visibility,
        team_id=team_id,
    )
    db.add(provider)
    await db.flush()
    return provider


async def _team_with_member(db: AsyncSession, name: str, owner_id: int, member_id: int) -> int:
    team = Team(name=name, owner_user_id=owner_id)
    db.add(team)
    await db.flush()
    db.add(TeamMember(team_id=team.id, user_id=owner_id, role="lead"))
    db.add(TeamMember(team_id=team.id, user_id=member_id, role="member"))
    await db.flush()
    return team.id


class TestVisibilityMatrix:
    async def test_owner_sees_own_private(self, db_session: AsyncSession):
        await _provider(
            db_session,
            name="own",
            category=ProviderCategory.private,
            owner_user_id=7,
            visibility=ProviderVisibility.owner,
        )
        providers = await ProviderService(db_session).list_providers(_user(7, OPERATOR))
        assert any(p.name == "own" for p in providers)

    async def test_member_sees_team_shared(self, db_session: AsyncSession):
        team_id = await _team_with_member(db_session, "team-v", owner_id=7, member_id=8)
        await _provider(
            db_session,
            name="team-shared",
            category=ProviderCategory.private,
            owner_user_id=7,
            visibility=ProviderVisibility.team,
            team_id=team_id,
        )
        providers = await ProviderService(db_session).list_providers(_user(8, OPERATOR))
        assert any(p.name == "team-shared" for p in providers)

    async def test_outsider_does_not_see_team_shared(self, db_session: AsyncSession):
        team_id = await _team_with_member(db_session, "team-x", owner_id=7, member_id=8)
        await _provider(
            db_session,
            name="team-hidden",
            category=ProviderCategory.private,
            owner_user_id=7,
            visibility=ProviderVisibility.team,
            team_id=team_id,
        )
        providers = await ProviderService(db_session).list_providers(_user(9, OPERATOR))
        assert all(p.name != "team-hidden" for p in providers)

    async def test_public_private_visible_to_all(self, db_session: AsyncSession):
        await _provider(
            db_session,
            name="public-private",
            category=ProviderCategory.private,
            owner_user_id=7,
            visibility=ProviderVisibility.public,
        )
        providers = await ProviderService(db_session).list_providers(_user(9, OPERATOR))
        assert any(p.name == "public-private" for p in providers)

    async def test_system_hidden_from_regular(self, db_session: AsyncSession):
        await _provider(
            db_session,
            name="system-hidden",
            category=ProviderCategory.system,
            owner_user_id=None,
            visibility=ProviderVisibility.owner,
        )
        providers = await ProviderService(db_session).list_providers(_user(8, OPERATOR))
        assert all(p.name != "system-hidden" for p in providers)

    async def test_system_visible_to_admin(self, db_session: AsyncSession):
        await _provider(
            db_session,
            name="system-visible",
            category=ProviderCategory.system,
            owner_user_id=None,
            visibility=ProviderVisibility.owner,
        )
        providers = await ProviderService(db_session).list_providers(_user(1, ADMIN))
        assert any(p.name == "system-visible" for p in providers)
