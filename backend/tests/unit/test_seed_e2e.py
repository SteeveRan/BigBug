"""
@file test_seed_e2e.py
@description Unit tests for the e2e account seeder: creates accounts with the
             expected roles/verify-able passwords, is idempotent (double run
             updates instead of failing), and resets drifted passwords/roles.
@dependencies backend/scripts/seed_e2e.py, backend/tests/conftest.py
"""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.role import Role, UserRole
from app.models.user import User
from scripts.seed_e2e import E2E_ACCOUNTS, seed_e2e_users


@pytest.fixture
async def default_roles(db_session: AsyncSession):
    """Ensure admin/viewer/operator roles exist (migrations do this in prod)."""
    for name in ("admin", "viewer", "operator"):
        result = await db_session.execute(select(Role).where(Role.name == name))
        if result.scalar_one_or_none() is None:
            db_session.add(Role(name=name, description=name))
    await db_session.commit()


async def _users(session: AsyncSession) -> dict[str, User]:
    result = await session.execute(select(User))
    return {u.username: u for u in result.scalars().all()}


async def test_creates_accounts_with_roles(db_session: AsyncSession, default_roles):
    actions = await seed_e2e_users(db_session)
    assert actions == [f"create {s['username']}" for s in E2E_ACCOUNTS]

    users = await _users(db_session)
    for spec in E2E_ACCOUNTS:
        user = users[spec["username"]]
        assert user.is_active is True
        assert verify_password(spec["password"], user.hashed_password)
        role_names = {r.name for r in user.roles}
        assert spec["role"] in role_names


async def test_double_run_is_idempotent(db_session: AsyncSession, default_roles):
    await seed_e2e_users(db_session)
    second = await seed_e2e_users(db_session)
    assert second == [f"update {s['username']}" for s in E2E_ACCOUNTS]

    count = (await db_session.execute(select(func.count()).select_from(User))).scalar_one()
    assert count == len(E2E_ACCOUNTS)


async def test_rotates_drifted_password_and_roles(db_session: AsyncSession, default_roles):
    await seed_e2e_users(db_session)

    # Simulate drift: password changed + extra role assigned.
    result = await db_session.execute(
        select(User).where(User.username == E2E_ACCOUNTS[0]["username"])
    )
    user = result.scalar_one()
    user.hashed_password = get_password_hash("someone-changed-me")
    operator_role = (
        await db_session.execute(select(Role).where(Role.name == "operator"))
    ).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=operator_role.id))
    await db_session.commit()

    await seed_e2e_users(db_session)

    result = await db_session.execute(
        select(User).where(User.username == E2E_ACCOUNTS[0]["username"])
    )
    user = result.scalar_one()
    assert verify_password(E2E_ACCOUNTS[0]["password"], user.hashed_password)
    assert {r.name for r in user.roles} == {E2E_ACCOUNTS[0]["role"]}
