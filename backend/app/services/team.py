"""
@file team.py
@description TeamService — teams and membership business logic (12.1.4, 12.3).
             Enforces the lead-membership invariant, atomic lead transfer,
             soft delete + provider unsharing, and member invite/remove rules.
             Raises :class:`app.core.exceptions.DomainError` for the API layer.
@dependencies sqlalchemy, app.models.team, app.models.team_member,
              app.models.resource_provider, app.core.exceptions
@relatedFiles ../api/teams.py, ../models/team.py, ../models/team_member.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DomainError
from app.models.resource_provider import ProviderVisibility, ResourceProvider
from app.models.team import Team, TeamRole
from app.models.team_member import TeamMember
from app.models.user import User


class TeamService:
    """Business logic for teams and team membership."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Queries ─────────────────────────────────────────────────────────

    async def _get_or_404(self, team_id: int) -> Team:
        team = await self.db.get(Team, team_id)
        if team is None or team.is_deleted:
            raise DomainError(f"Team {team_id} not found", 404)
        return team

    async def _get_member(self, team_id: int, user_id: int) -> TeamMember | None:
        return await self.db.get(TeamMember, (team_id, user_id))

    async def _is_admin(self, user: User) -> bool:
        cached = getattr(user, "_cached_permissions", [])
        if cached:
            return "providers:read_all" in cached
        from app.services.rbac_service import RBACService

        perms = await RBACService(self.db).get_user_permissions(user.id)
        return "providers:read_all" in perms

    async def _members_count(self, team_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(TeamMember).where(TeamMember.team_id == team_id)
        )
        return int(result.scalar() or 0)

    async def _ensure_member(self, team_id: int, user: User) -> TeamMember:
        """Return the caller's membership row or raise 403."""
        member = await self._get_member(team_id, user.id)
        if member is None:
            raise DomainError("Access denied: not a member of this team", 403)
        return member

    # ── Team CRUD ───────────────────────────────────────────────────────

    async def create_team(self, name: str, description: str | None, owner_user_id: int) -> Team:
        owner = await self.db.get(User, owner_user_id)
        if owner is None:
            raise DomainError(f"User {owner_user_id} not found", 422)

        existing = await self.db.execute(
            select(Team).where(Team.name == name, Team.is_deleted.is_(False))
        )
        if existing.scalar_one_or_none() is not None:
            raise DomainError(f"Team name '{name}' already exists", 409)

        team = Team(name=name, description=description, owner_user_id=owner_user_id)
        self.db.add(team)
        await self.db.flush()

        # Invariant 12.1.4-1: the lead's membership is always a row with role=lead.
        self.db.add(TeamMember(team_id=team.id, user_id=owner_user_id, role=TeamRole.lead))

        await self.db.commit()
        await self.db.refresh(team)
        return team

    async def update_team(
        self,
        team_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        owner_user_id: int | None = None,
    ) -> Team:
        team = await self._get_or_404(team_id)

        if name is not None and name != team.name:
            existing = await self.db.execute(
                select(Team).where(Team.name == name, Team.is_deleted.is_(False))
            )
            if existing.scalar_one_or_none() is not None:
                raise DomainError(f"Team name '{name}' already exists", 409)
            team.name = name
        if description is not None:
            team.description = description

        if owner_user_id is not None and owner_user_id != team.owner_user_id:
            new_owner = await self.db.get(User, owner_user_id)
            if new_owner is None:
                raise DomainError(f"User {owner_user_id} not found", 422)

            # Atomic lead transfer: new owner becomes lead, old owner becomes member.
            new_owner_member = await self._get_member(team.id, owner_user_id)
            if new_owner_member is None:
                self.db.add(TeamMember(team_id=team.id, user_id=owner_user_id, role=TeamRole.lead))
            else:
                new_owner_member.role = TeamRole.lead

            old_owner_member = await self._get_member(team.id, team.owner_user_id)
            if old_owner_member is not None:
                old_owner_member.role = TeamRole.member

            team.owner_user_id = owner_user_id

        await self.db.commit()
        await self.db.refresh(team)
        return team

    async def delete_team(self, team_id: int) -> None:
        team = await self._get_or_404(team_id)

        # 12.1.4-3: revoke sharing before soft-deleting the team.
        team_providers = (
            (
                await self.db.execute(
                    select(ResourceProvider).where(ResourceProvider.team_id == team_id)
                )
            )
            .scalars()
            .all()
        )
        for provider in team_providers:
            provider.visibility = ProviderVisibility.owner
            provider.team_id = None

        team.is_deleted = True
        team.deleted_at = datetime.now(UTC)
        await self.db.commit()

    # ── Membership ──────────────────────────────────────────────────────

    async def list_teams(self, user: User, all_teams: bool = False) -> list[Team]:
        stmt = select(Team).where(Team.is_deleted.is_(False))
        if not all_teams and not await self._is_admin(user):
            stmt = stmt.where(
                Team.id.in_(select(TeamMember.team_id).where(TeamMember.user_id == user.id))
            )
        result = await self.db.execute(stmt.order_by(Team.name))
        return list(result.scalars().all())

    async def get_team_card(self, team_id: int, user: User) -> dict:
        team = await self._get_or_404(team_id)
        is_admin = await self._is_admin(user)
        member = await self._get_member(team_id, user.id)
        if not is_admin and member is None:
            raise DomainError("Access denied: not a member of this team", 403)

        owner = await self.db.get(User, team.owner_user_id)
        return {
            "id": team.id,
            "name": team.name,
            "description": team.description,
            "owner": {"id": owner.id, "username": owner.username} if owner else None,
            "members_count": await self._members_count(team.id),
            "my_role": member.role if member is not None else None,
        }

    async def add_member(self, team_id: int, user_id: int) -> TeamMember:
        await self._get_or_404(team_id)
        target = await self.db.get(User, user_id)
        if target is None:
            raise DomainError(f"User {user_id} not found", 422)

        if await self._get_member(team_id, user_id) is not None:
            raise DomainError(f"User {user_id} is already a member", 409)

        self.db.add(TeamMember(team_id=team_id, user_id=user_id, role=TeamRole.member))
        await self.db.commit()

        result = await self.db.execute(
            select(TeamMember)
            .options(selectinload(TeamMember.user))
            .where(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        )
        return result.scalar_one()

    async def remove_member(self, team_id: int, user_id: int, actor: User) -> None:
        team = await self._get_or_404(team_id)
        member = await self._get_member(team_id, user_id)
        if member is None:
            raise DomainError(f"User {user_id} is not a member", 404)

        # Lead cannot be removed — ownership must be transferred first (12.3).
        if user_id == team.owner_user_id:
            raise DomainError("Cannot remove the team lead; transfer ownership first", 400)

        # Self-exit is always allowed; removing another member requires lead/admin
        # (the API layer enforces this via scope + lead-check).
        is_self = user_id == actor.id
        actor_member = await self._get_member(team_id, actor.id)
        is_lead = actor_member is not None and actor_member.role == TeamRole.lead
        if not is_self and not is_lead and not await self._is_admin(actor):
            raise DomainError("Access denied: only the lead can remove members", 403)

        await self.db.delete(member)

        # 12.1.4-4: if the removed member owned team-shared providers in this team,
        # reset them to owner visibility (they lose the team context).
        owned = (
            (
                await self.db.execute(
                    select(ResourceProvider).where(
                        ResourceProvider.team_id == team_id,
                        ResourceProvider.owner_user_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for provider in owned:
            provider.visibility = ProviderVisibility.owner
            provider.team_id = None

        await self.db.commit()

    async def list_members(self, team_id: int) -> list[TeamMember]:
        await self._get_or_404(team_id)
        result = await self.db.execute(
            select(TeamMember)
            .options(selectinload(TeamMember.user))
            .where(TeamMember.team_id == team_id)
            .order_by(TeamMember.joined_at, TeamMember.user_id)
        )
        return list(result.scalars().all())

    async def list_team_providers(self, team_id: int) -> list[ResourceProvider]:
        await self._get_or_404(team_id)
        result = await self.db.execute(
            select(ResourceProvider)
            .options(selectinload(ResourceProvider.team))
            .where(
                ResourceProvider.team_id == team_id,
                ResourceProvider.is_deleted.is_(False),
            )
            .order_by(ResourceProvider.name)
        )
        return list(result.scalars().all())
