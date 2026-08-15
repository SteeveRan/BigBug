"""
@file test_resource_provider_constraints.py
@description Unit tests for ResourceProvider DB constraints (stage 2): CHECK
             category=private → owner_user_id NOT NULL, partial unique name and
             partial unique default per scope.
@dependencies backend/app/models/resource_provider.py, backend/tests/conftest.py
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)


async def _create(
    db: AsyncSession,
    *,
    name: str,
    category=ProviderCategory.public,
    owner_user_id: int | None = None,
    is_default: bool = False,
    subtype=ProviderSubtype.github,
    direction=ProviderDirection.external,
):
    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=subtype,
        category=category,
        direction=direction,
        name=name,
        label=name,
        owner_user_id=owner_user_id,
        is_default=is_default,
    )
    db.add(provider)
    await db.flush()
    return provider


class TestPrivateOwnerCheck:
    async def test_private_without_owner_raises(self, db_session: AsyncSession):
        with pytest.raises(IntegrityError):
            await _create(db_session, name="p1", category=ProviderCategory.private)
        await db_session.rollback()

    async def test_private_with_owner_ok(self, db_session: AsyncSession):
        p = await _create(db_session, name="p2", category=ProviderCategory.private, owner_user_id=1)
        assert p.id is not None


class TestUniqueNamePartial:
    async def test_duplicate_live_name_raises(self, db_session: AsyncSession):
        await _create(db_session, name="dup")
        await db_session.flush()
        with pytest.raises(IntegrityError):
            await _create(db_session, name="dup")
        await db_session.rollback()

    async def test_soft_deleted_name_can_be_reused(self, db_session: AsyncSession):
        p = await _create(db_session, name="reuse")
        p.is_deleted = True
        await db_session.flush()
        # Reuse the same name while the first row is soft-deleted.
        p2 = await _create(db_session, name="reuse")
        assert p2.id != p.id


class TestUniqueDefaultPerScope:
    async def test_second_default_in_scope_raises(self, db_session: AsyncSession):
        await _create(
            db_session,
            name="d1",
            category=ProviderCategory.private,
            owner_user_id=1,
            is_default=True,
        )
        await db_session.flush()
        with pytest.raises(IntegrityError):
            await _create(
                db_session,
                name="d2",
                category=ProviderCategory.private,
                owner_user_id=2,
                is_default=True,
            )
        await db_session.rollback()

    async def test_default_in_different_scope_ok(self, db_session: AsyncSession):
        await _create(
            db_session,
            name="s1",
            category=ProviderCategory.private,
            owner_user_id=1,
            is_default=True,
        )
        # Different subtype → different scope.
        p = await _create(
            db_session,
            name="s2",
            category=ProviderCategory.private,
            owner_user_id=2,
            is_default=True,
            subtype=ProviderSubtype.gitlab,
        )
        assert p.id is not None
