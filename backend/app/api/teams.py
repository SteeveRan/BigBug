"""
@file teams.py
@description REST API for teams (12.3): CRUD, membership management and
             team provider listing. Maps :class:`app.core.exceptions.DomainError`
             raised by :class:`app.services.team.TeamService` to HTTP responses.
@dependencies app.core.rbac, app.schemas.team, app.services.team
@relatedFiles ../models/team.py, ../models/team_member.py, ../services/team.py
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.core.rbac import (
    get_current_user,
    require_permission,
    require_scope_permission,
)
from app.database import get_db
from app.models.team_member import TeamMember
from app.models.user import User
from app.schemas.provider import ProviderOut
from app.schemas.team import (
    TeamCreate,
    TeamMemberAdd,
    TeamMemberOut,
    TeamOut,
    TeamUpdate,
)
from app.services.rbac_service import RBACService
from app.services.team import TeamService

router = APIRouter()


def _translate(exc: DomainError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _member_out(member: TeamMember) -> TeamMemberOut:
    username = member.user.username if member.user is not None else f"user_{member.user_id}"
    return TeamMemberOut(
        user_id=member.user_id,
        username=username,
        role=member.role,
        joined_at=member.joined_at,
    )


async def _require_lead_or_admin(db: AsyncSession, current_user: User, team_id: int) -> None:
    """Membership mutations require lead role or admin (12.2.3)."""
    perms = await _user_permissions(current_user, db)
    if "teams:manage_members" in perms and "providers:read_all" in perms:
        # admin holds both; read_all implies admin
        return
    if await RBACService(db).is_team_lead(current_user.id, team_id):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the team lead can manage members",
    )


async def _user_permissions(user: User, db: AsyncSession) -> set[str]:
    cached = getattr(user, "_cached_permissions", [])
    if cached:
        return set(cached)
    return set(await RBACService(db).get_user_permissions(user.id))


# ──── Team CRUD ────────────────────────────────────────────────────────────


@router.get("", response_model=list[TeamOut])
async def list_teams(
    all: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("teams:read")),
):
    service = TeamService(db)
    teams = await service.list_teams(current_user, all_teams=all)
    out: list[TeamOut] = []
    for team in teams:
        card = await service.get_team_card(team.id, current_user)
        out.append(TeamOut(**card))
    return out


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
async def create_team(
    data: TeamCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("teams:write")),
):
    service = TeamService(db)
    try:
        team = await service.create_team(data.name, data.description, data.owner_user_id)
        card = await service.get_team_card(team.id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc
    return TeamOut(**card)


@router.get("/{team_id}", response_model=TeamOut)
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("teams:read")),
):
    service = TeamService(db)
    try:
        card = await service.get_team_card(team_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc
    return TeamOut(**card)


@router.patch("/{team_id}", response_model=TeamOut)
async def update_team(
    team_id: int,
    data: TeamUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("teams:write")),
):
    service = TeamService(db)
    try:
        team = await service.update_team(
            team_id,
            name=data.name,
            description=data.description,
            owner_user_id=data.owner_user_id,
        )
        card = await service.get_team_card(team.id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc
    return TeamOut(**card)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("teams:write")),
):
    service = TeamService(db)
    try:
        await service.delete_team(team_id)
    except DomainError as exc:
        raise _translate(exc) from exc


# ──── Membership ───────────────────────────────────────────────────────────


@router.get("/{team_id}/members", response_model=list[TeamMemberOut])
async def list_members(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List team members — requires read permission plus membership scope."""
    perms = await _user_permissions(current_user, db)
    if "teams:read" not in perms:
        raise HTTPException(status_code=403, detail="Permission denied: 'teams:read' required")
    if "providers:read_all" not in perms and not await RBACService(db).check_scope_access(
        current_user.id, "team", team_id
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    service = TeamService(db)
    try:
        members = await service.list_members(team_id)
    except DomainError as exc:
        raise _translate(exc) from exc
    return [_member_out(m) for m in members]


@router.post(
    "/{team_id}/members",
    response_model=TeamMemberOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    team_id: int,
    data: TeamMemberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("teams:manage_members", "team", "team_id")),
):
    await _require_lead_or_admin(db, current_user, team_id)
    service = TeamService(db)
    try:
        member = await service.add_member(team_id, data.user_id)
    except DomainError as exc:
        raise _translate(exc) from exc
    return _member_out(member)


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    team_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _: bool = Depends(require_scope_permission("teams:manage_members", "team", "team_id")),
):
    await _require_lead_or_admin(db, current_user, team_id)
    service = TeamService(db)
    try:
        await service.remove_member(team_id, user_id, current_user)
    except DomainError as exc:
        raise _translate(exc) from exc


# ──── Team providers ───────────────────────────────────────────────────────


@router.get("/{team_id}/providers", response_model=list[ProviderOut])
async def list_team_providers(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    perms = await _user_permissions(current_user, db)
    if "teams:read" not in perms:
        raise HTTPException(status_code=403, detail="Permission denied: 'teams:read' required")
    if "providers:read_all" not in perms and not await RBACService(db).check_scope_access(
        current_user.id, "team", team_id
    ):
        raise HTTPException(
            status_code=403, detail="Access denied: resource not in your role scope"
        )

    service = TeamService(db)
    try:
        providers = await service.list_team_providers(team_id)
    except DomainError as exc:
        raise _translate(exc) from exc
    return [ProviderOut.model_validate(p) for p in providers]
