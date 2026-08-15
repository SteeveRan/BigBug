"""
@file test_seed_providers.py
@description Unit tests for the default provider seeder (stage 10): --dry-run writes
             nothing, double run yields zero duplicates, the four section-5.2 records
             are correct, they are protected, and no system provider is created.
@dependencies backend/scripts/seed_providers.py, backend/tests/conftest.py
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource_provider import ProviderCategory, ResourceProvider
from scripts.seed_providers import DEFAULT_PROVIDERS, seed_providers

_EXPECTED_BY_NAME = {spec["name"]: spec for spec in DEFAULT_PROVIDERS}


async def _count(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(ResourceProvider))).scalar_one()


async def _all(session: AsyncSession) -> list[ResourceProvider]:
    result = await session.execute(select(ResourceProvider).order_by(ResourceProvider.name))
    return list(result.scalars().all())


class TestDryRun:
    async def test_dry_run_writes_nothing(self, db_session: AsyncSession):
        actions = await seed_providers(db_session, dry_run=True)
        assert len(actions) == len(DEFAULT_PROVIDERS)
        assert await _count(db_session) == 0


class TestIdempotency:
    async def test_double_run_no_duplicates(self, db_session: AsyncSession):
        first = await seed_providers(db_session)
        assert len(first) == len(DEFAULT_PROVIDERS)
        assert await _count(db_session) == len(DEFAULT_PROVIDERS)

        second = await seed_providers(db_session)
        assert second == []
        assert await _count(db_session) == len(DEFAULT_PROVIDERS)


class TestSeedContent:
    async def test_four_records_correct(self, db_session: AsyncSession):
        await seed_providers(db_session)

        providers = {p.name: p for p in await _all(db_session)}
        assert set(providers) == set(_EXPECTED_BY_NAME)

        for name, spec in _EXPECTED_BY_NAME.items():
            p = providers[name]
            assert p.domain == spec["domain"]
            assert p.subtype == spec["subtype"]
            assert p.category == spec["category"]
            assert p.direction == spec["direction"]
            assert p.base_url == spec["base_url"]

    async def test_all_protected(self, db_session: AsyncSession):
        await seed_providers(db_session)
        providers = await _all(db_session)
        assert len(providers) == len(DEFAULT_PROVIDERS)
        assert all(p.is_protected is True for p in providers)
        assert all(p.is_default is True for p in providers)

    async def test_system_not_created(self, db_session: AsyncSession):
        await seed_providers(db_session)
        result = await db_session.execute(
            select(func.count())
            .select_from(ResourceProvider)
            .where(ResourceProvider.category == ProviderCategory.system)
        )
        assert result.scalar_one() == 0


class TestUpdateSeededFields:
    async def test_only_seeded_fields_are_overwritten(self, db_session: AsyncSession):
        # Pre-existing row with the seed name but user-customised fields.
        existing = ResourceProvider(
            domain=_EXPECTED_BY_NAME["github-anonymous"]["domain"],
            subtype=_EXPECTED_BY_NAME["github-anonymous"]["subtype"],
            category=ProviderCategory.public,
            direction=_EXPECTED_BY_NAME["github-anonymous"]["direction"],
            name="github-anonymous",
            label="My custom label",
            base_url="https://custom.example.com",
            config={"custom": True},
            is_protected=False,
            is_default=False,
        )
        db_session.add(existing)
        await db_session.commit()

        actions = await seed_providers(db_session)
        # The pre-existing github-anonymous row is updated; the other three
        # seeded defaults are created in the same pass.
        update = next(a for a in actions if a["name"] == "github-anonymous")
        assert update == {
            "action": "update",
            "name": "github-anonymous",
            "fields": sorted(["label", "is_default", "is_protected"]),
        }
        assert {a["name"] for a in actions if a["action"] == "create"} == (
            set(_EXPECTED_BY_NAME) - {"github-anonymous"}
        )

        await db_session.refresh(existing)
        assert existing.label == _EXPECTED_BY_NAME["github-anonymous"]["label"]
        assert existing.is_protected is True
        assert existing.is_default is True
        # Non-seeded fields are preserved.
        assert existing.base_url == "https://custom.example.com"
        assert existing.config == {"custom": True}
