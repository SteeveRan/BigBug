"""
@file test_seed_providers.py
@description Unit tests for the default provider seeder (stage 10): --dry-run writes
             nothing, double run yields zero duplicates, the four section-5.2 records
             are correct, they are protected, and no system provider is created.
@dependencies backend/scripts/seed_providers.py, backend/tests/conftest.py
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import decrypt_secret
from app.models.credential import Credential
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderSubtype,
    ResourceProvider,
)
from scripts.seed_providers import (
    DEFAULT_PROVIDERS,
    HARBOR_SYSTEM_CREDENTIAL_NAME,
    HARBOR_SYSTEM_PROVIDER_NAME,
    _harbor_env,
    _seed_system_harbor,
    seed_providers,
)

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


# ─── Harbor system provider (env-gated) ──────────────────────────────────────


def _set_harbor_env(monkeypatch, **overrides):
    monkeypatch.setenv("HARBOR_URL", "https://harbor.example.com")
    monkeypatch.setenv("HARBOR_USERNAME", "robot$bigbug")
    monkeypatch.setenv("HARBOR_PASSWORD", "hunter2")
    monkeypatch.setenv("HARBOR_DEFAULT_PROJECT", "bigbug")
    monkeypatch.setenv("HARBOR_PROJECTS_ALLOWLIST", "bigbug,shared")
    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


class TestHarborEnv:
    def test_returns_none_without_harbor_url(self, monkeypatch):
        monkeypatch.delenv("HARBOR_URL", raising=False)
        assert _harbor_env() is None

    def test_parses_env(self, monkeypatch):
        _set_harbor_env(monkeypatch)
        env = _harbor_env()
        assert env["base_url"] == "https://harbor.example.com"
        assert env["username"] == "robot$bigbug"
        assert env["password"] == "hunter2"
        assert env["default_project"] == "bigbug"
        assert env["projects_allowlist"] == ["bigbug", "shared"]
        assert env["verify_ssl"] is True

    def test_verify_ssl_false(self, monkeypatch):
        _set_harbor_env(monkeypatch, HARBOR_VERIFY_SSL="false")
        assert _harbor_env()["verify_ssl"] is False


class TestSeedSystemHarbor:
    async def test_creates_credential_and_provider(self, db_session: AsyncSession, monkeypatch):
        _set_harbor_env(monkeypatch)

        actions = await _seed_system_harbor(db_session, dry_run=False)
        await db_session.commit()

        create_names = {a["name"] for a in actions if a["action"] == "create"}
        assert HARBOR_SYSTEM_CREDENTIAL_NAME in create_names
        assert HARBOR_SYSTEM_PROVIDER_NAME in create_names

        cred = (
            await db_session.execute(
                select(Credential).where(Credential.name == HARBOR_SYSTEM_CREDENTIAL_NAME)
            )
        ).scalar_one()
        assert cred.credential_type.value == "https_basic"
        assert cred.username == "robot$bigbug"
        assert decrypt_secret(cred.encrypted_secret) == "hunter2"

        provider = (
            await db_session.execute(
                select(ResourceProvider).where(
                    ResourceProvider.name == HARBOR_SYSTEM_PROVIDER_NAME
                )
            )
        ).scalar_one()
        assert provider.domain.value == "docker"
        assert provider.subtype == ProviderSubtype.harbor
        assert provider.category == ProviderCategory.system
        assert provider.direction == ProviderDirection.internal
        assert provider.base_url == "https://harbor.example.com"
        assert provider.config == {
            "default_project": "bigbug",
            "robot_prefix": "robot$",
            "projects_allowlist": ["bigbug", "shared"],
        }
        assert provider.is_protected is True
        assert provider.is_default is True

    async def test_idempotent(self, db_session: AsyncSession, monkeypatch):
        _set_harbor_env(monkeypatch)

        first = await _seed_system_harbor(db_session, dry_run=False)
        await db_session.commit()
        assert first

        second = await _seed_system_harbor(db_session, dry_run=False)
        await db_session.commit()
        assert second == []

    async def test_rotates_password_without_ciphertext_churn(
        self, db_session: AsyncSession, monkeypatch
    ):
        _set_harbor_env(monkeypatch)
        await _seed_system_harbor(db_session, dry_run=False)
        await db_session.commit()

        # Same password again → no encrypted_secret churn (Fernet tokens differ
        # per call, but the plaintext is equal so the seed must not rotate).
        second = await _seed_system_harbor(db_session, dry_run=False)
        await db_session.commit()
        assert not any("encrypted_secret" in a.get("fields", []) for a in second)

        # Different password → rotation.
        _set_harbor_env(monkeypatch, HARBOR_PASSWORD="new-secret")
        third = await _seed_system_harbor(db_session, dry_run=False)
        await db_session.commit()
        assert any("encrypted_secret" in a.get("fields", []) for a in third)
