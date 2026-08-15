"""
@file test_provider_service_crud.py
@description Unit tests for ProviderService (stage 5): CRUD, duplicate name 409,
             is_default switching, is_protected delete 409, private visibility,
             system mutation requires providers_system:write.
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
)
from app.models.user import User
from app.services.providers.service import ProviderService


def _user(user_id: int, permissions: list[str]) -> User:
    user = User(username=f"u{user_id}", email=f"u{user_id}@test.com")
    user.id = user_id
    user._cached_permissions = permissions
    return user


ADMIN = [
    "providers:read",
    "providers:write",
    "providers:delete",
    "providers:read_all",
    "providers_system:write",
]
OPERATOR = ["providers:read", "providers:write", "providers:use"]
SYSTEM_ADMIN = ["providers:read", "providers_system:write"]


class TestCreate:
    async def test_create_public(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        p = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="gh",
            label="GitHub",
            user=_user(1, ADMIN),
        )
        assert p.id is not None
        assert p.owner_user_id is None

    async def test_create_private_sets_owner(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        p = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="gitlab",
            label="GitLab",
            user=_user(7, ADMIN),
        )
        assert p.owner_user_id == 7

    async def test_duplicate_name_conflict(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="dup",
            label="A",
            user=_user(1, ADMIN),
        )
        with pytest.raises(DomainError) as exc:
            await svc.create_provider(
                domain=ProviderDomain.git,
                subtype=ProviderSubtype.github,
                category=ProviderCategory.public,
                direction=ProviderDirection.external,
                name="dup",
                label="B",
                user=_user(1, ADMIN),
            )
        assert exc.value.status_code == 409

    async def test_system_requires_system_permission(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        with pytest.raises(DomainError) as exc:
            await svc.create_provider(
                domain=ProviderDomain.git,
                subtype=ProviderSubtype.gitlab,
                category=ProviderCategory.system,
                direction=ProviderDirection.internal,
                name="sys-gitlab",
                label="GitLab",
                user=_user(2, OPERATOR),
            )
        assert exc.value.status_code == 403


class TestUpdateDefault:
    async def test_switch_default_unsets_previous(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        first = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="one",
            label="One",
            user=_user(1, ADMIN),
        )
        second = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="two",
            label="Two",
            user=_user(1, ADMIN),
        )
        await svc.update_provider(first.id, _user(1, ADMIN), is_default=True)
        await db_session.refresh(first)
        await svc.update_provider(second.id, _user(1, ADMIN), is_default=True)
        await db_session.refresh(first)
        await db_session.refresh(second)
        assert second.is_default is True
        assert first.is_default is False

    async def test_operator_cannot_set_default(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        provider = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="operator-default",
            label="Operator Default",
            user=_user(1, ADMIN),
        )
        with pytest.raises(DomainError) as exc:
            await svc.update_provider(provider.id, _user(2, OPERATOR), is_default=True)
        assert exc.value.status_code == 403

    async def test_admin_can_set_default(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        provider = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.github,
            category=ProviderCategory.public,
            direction=ProviderDirection.external,
            name="admin-default",
            label="Admin Default",
            user=_user(1, ADMIN),
        )
        updated = await svc.update_provider(provider.id, _user(1, ADMIN), is_default=True)
        await db_session.refresh(updated)
        assert updated.is_default is True


class TestDelete:
    async def test_protected_delete_conflict(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        p = await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.system,
            direction=ProviderDirection.internal,
            name="sys",
            label="System GitLab",
            user=_user(1, ADMIN),
        )
        assert p.is_protected is True
        with pytest.raises(DomainError) as exc:
            await svc.delete_provider(p.id, _user(1, ADMIN))
        assert exc.value.status_code == 409


class TestSystemVisibility:
    async def test_system_provider_visible_without_read_all(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.system,
            direction=ProviderDirection.internal,
            name="sys-visible",
            label="System GitLab",
            user=_user(1, ADMIN),
        )
        providers = await svc.list_providers(_user(2, SYSTEM_ADMIN))
        assert any(p.name == "sys-visible" for p in providers)


class TestVisibility:
    async def test_private_hidden_from_other_user(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="private-1",
            label="Private",
            user=_user(7, ADMIN),
        )
        other = _user(8, OPERATOR)
        providers = await svc.list_providers(other)
        assert all(p.name != "private-1" for p in providers)

    async def test_private_visible_to_read_all(self, db_session: AsyncSession):
        svc = ProviderService(db_session)
        await svc.create_provider(
            domain=ProviderDomain.git,
            subtype=ProviderSubtype.gitlab,
            category=ProviderCategory.private,
            direction=ProviderDirection.external,
            name="private-2",
            label="Private",
            user=_user(7, ADMIN),
        )
        admin = _user(9, ADMIN)
        providers = await svc.list_providers(admin)
        assert any(p.name == "private-2" for p in providers)
