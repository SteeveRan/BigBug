"""
@file test_providers_migration.py
@description Stage 14 unit tests for the phase-3 data migration (00932f2a02d5):
             legacy instance tables + source_providers → resource_providers,
             secret transfer (ciphertext as-is + plaintext fallback), FK relink,
             downgrade and idempotency. Runs the real Alembic chain against a
             throwaway PostgreSQL database (skipped when PG is unavailable).
@dependencies alembic, asyncpg, backend/alembic/versions/20260814_2100_00932f2a02d5_*.py
"""

import asyncio
import importlib.util
import json
import os
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config as AlembicConfig
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from app.config import settings

# ── Test-environment constants ──────────────────────────────────────────────

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_DIR = BACKEND_DIR / "alembic"

# Reuse the project's test Fernet key (same as unit/conftest.py) so the
# migration's encrypt/decrypt helpers (patched via the autouse fixture) and
# this module's Fernet instance agree.
KEY = "Z0lZSjZpc3gyMDI1Y29vbHByb2plY3RmZXJuZXRrZXk="
FERNET = Fernet(KEY.encode())

PG_HOST_DSN = os.environ.get("BIGBUG_MIGTEST_PG", "bigbug:bigbug@localhost:5432")
TEST_DB = "bigbug_mig_test_pytest"
ADMIN_URL = f"postgresql://{PG_HOST_DSN}/postgres"
TEST_URL = f"postgresql+asyncpg://{PG_HOST_DSN}/{TEST_DB}"

# Revision before the data migration (phase-1 DDL + 0T already applied) and
# the phase-3 revision itself.
PRE_PHASE3 = "78cd1e526b72"
PHASE3 = "00932f2a02d5"

# Alembic runs one command in a single transaction; e5f6a7b8c9d0 ALTERs the
# enum via a separate connection and cannot see the enum created earlier in
# the same uncommitted transaction. Splitting the chain here commits the enum
# first (same limitation applies to any fresh `upgrade head` from scratch —
# the standard init path runs the chain in several steps).
PRE_ENUM_SPLIT = "dc0ef2cfb148"

_MIGRATION_PATH = next((ALEMBIC_DIR / "versions").glob("20260814_2100_00932f2a02d5_*.py"))

# Secrets used by the seed (all Fernet-encrypted except the fallback case).
PLAINTEXT_FALLBACK = "pre-fernet-plaintext-password"


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_phase3", _MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _with_admin(coro_fn):
    conn = await asyncpg.connect(ADMIN_URL)
    try:
        return await coro_fn(conn)
    finally:
        await conn.close()


async def _connect_test_db():
    return await asyncpg.connect(f"postgresql://{PG_HOST_DSN}/{TEST_DB}")


def _alembic_config() -> AlembicConfig:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    return cfg


# ── Seed (mirrors a realistic pre-phase-3 database) ─────────────────────────


async def _seed(conn: asyncpg.Connection) -> None:
    for table in [
        "helm_chart_sources",
        "docker_image_sources",
        "pipelines",
        "source_repositories",
        "source_providers",
        "helm_repository_instances",
        "docker_registry_instances",
        "harbor_instances",
        "github_instances",
        "gitlab_instances",
        "credentials",
        "user_roles",
        "users",
        "roles",
    ]:
        await conn.execute(f"TRUNCATE {table} RESTART IDENTITY CASCADE")

    role_id = await conn.fetchval(
        "INSERT INTO roles (name, description, is_custom, created_at) "
        "VALUES ('admin', 'Administrator', false, now()) RETURNING id"
    )
    admin_id = await conn.fetchval(
        "INSERT INTO users (username, email, hashed_password, is_active, created_at, updated_at) "
        "VALUES ('migadmin', 'migadmin@bigbug.local', 'x', true, now(), now()) RETURNING id"
    )
    await conn.execute(
        "INSERT INTO user_roles (user_id, role_id, assigned_at) VALUES ($1, $2, now())",
        admin_id,
        role_id,
    )

    gitlab_token = FERNET.encrypt(b"gitlab-secret").decode()
    github_token = FERNET.encrypt(b"github-secret").decode()
    harbor_password = FERNET.encrypt(b"harbor-password").decode()
    docker_password = FERNET.encrypt(b"docker-password").decode()
    helm_password = FERNET.encrypt(b"helm-password").decode()

    # gitlab: default instance (→ system/internal) + external private one
    gli_default = await conn.fetchval(
        "INSERT INTO gitlab_instances (name, url, token, is_active, verify_ssl, "
        "is_default, default_group_id, status_flag, status_text, created_at, updated_at) "
        "VALUES ('platform-gitlab', 'http://gitlab.local', $1::text, true, true, "
        "true, 42, 0, 'OK', now(), now()) RETURNING id",
        gitlab_token,
    )
    await conn.fetchval(
        "INSERT INTO gitlab_instances (name, url, token, is_active, verify_ssl, "
        "is_default, status_flag, status_text, created_at, updated_at) "
        "VALUES ('ext-gitlab', 'https://gitlab.example.com', $1::text, true, false, "
        "false, 0, 'OK', now(), now())",
        gitlab_token,
    )

    await conn.fetchval(
        "INSERT INTO github_instances (name, token, is_active, is_default, "
        "status_flag, status_text, created_at, updated_at) "
        "VALUES ('my-github', $1::text, true, false, 0, 'OK', now(), now())",
        github_token,
    )

    await conn.fetchval(
        "INSERT INTO harbor_instances (name, url, username, password, is_active, "
        "verify_ssl, is_default, default_project, status_flag, status_text, "
        "created_at, updated_at) "
        "VALUES ('platform-harbor', 'https://harbor.local', 'admin', $1::text, true, "
        "true, true, 'default', 0, 'OK', now(), now())",
        harbor_password,
    )

    # docker registries: internal target (→ system) + external with a
    # pre-Fernet plaintext password (→ fallback branch of 11.1.3)
    dri_target = await conn.fetchval(
        "INSERT INTO docker_registry_instances (name, url, username, password, "
        "is_active, verify_ssl, is_default, registry_type, registry_provider, "
        "priority, status_flag, status_text, created_at, updated_at) "
        "VALUES ('target-registry', 'registry.internal.example.com', 'admin', $1::text, "
        "true, true, false, 'internal', 'generic', 0, 0, 'OK', now(), now()) RETURNING id",
        docker_password,
    )
    await conn.fetchval(
        "INSERT INTO docker_registry_instances (name, url, username, password, "
        "is_active, verify_ssl, is_default, registry_type, registry_provider, "
        "priority, status_flag, status_text, created_at, updated_at) "
        "VALUES ('dockerhub-private', 'registry-1.docker.io', 'user', $1::text, "
        "true, true, false, 'external', 'docker_hub', 5, 0, 'OK', now(), now())",
        PLAINTEXT_FALLBACK,
    )

    # helm: private (with secret) + public (no secret)
    await conn.fetchval(
        "INSERT INTO helm_repository_instances (name, url, username, password, "
        "is_active, verify_ssl, is_default, status_flag, status_text, created_at, updated_at) "
        "VALUES ('private-charts', 'https://charts.example.com', 'user', $1::text, "
        "true, true, false, 0, 'OK', now(), now())",
        helm_password,
    )
    await conn.fetchval(
        "INSERT INTO helm_repository_instances (name, url, username, password, "
        "is_active, verify_ssl, is_default, status_flag, status_text, created_at, updated_at) "
        "VALUES ('public-charts', 'https://charts.public.com', NULL, NULL, "
        "true, true, false, 0, 'OK', now(), now())"
    )

    # source_providers: anonymous builtin + private one reusing an existing credential
    cred_id = await conn.fetchval(
        "INSERT INTO credentials (name, credential_type, provider, username, "
        "encrypted_secret, status_flag, status_text, created_at, updated_at) "
        "VALUES ('existing-cred', 'github_token', 'github', NULL, $1::text, 0, 'OK', "
        "now(), now()) RETURNING id",
        FERNET.encrypt(b"existing-secret").decode(),
    )
    await conn.fetchval(
        "INSERT INTO source_providers (credential_id, provider_type, label, is_anon, "
        "is_builtin, is_deleted, created_at, updated_at) "
        "VALUES (NULL, 'github', 'GitHub (Anonymous)', true, true, false, now(), now())"
    )
    sp_private = await conn.fetchval(
        "INSERT INTO source_providers (credential_id, provider_type, label, is_anon, "
        "is_builtin, is_deleted, created_at, updated_at) "
        "VALUES ($1, 'gitlab', 'My GitLab', false, false, false, now(), now()) RETURNING id",
        cred_id,
    )

    # Consumers to relink
    await conn.fetchval(
        "INSERT INTO source_repositories (source_group_id, source_provider_id, "
        "external_id, name, full_name, is_deleted, created_at, updated_at) "
        "VALUES (NULL, $1, 'e1', 'repo1', 'org/repo1', false, now(), now())",
        sp_private,
    )
    await conn.fetchval(
        "INSERT INTO pipelines (name, gitlab_instance_id, ref, default_variables, "
        "is_default, is_enabled, created_at, updated_at) "
        "VALUES ('Default', $1, 'main', '{}', true, true, now(), now())",
        gli_default,
    )
    await conn.fetchval(
        "INSERT INTO docker_image_sources (name, registry_url, registry_instance_id, "
        "target_registry_url, status_flag, created_at, updated_at) "
        "VALUES ('img-src', 'registry.internal.example.com', $1, "
        "'registry.internal.example.com', 4, now(), now())",
        dri_target,
    )
    await conn.fetchval(
        "INSERT INTO helm_chart_sources (name, repo_url, status_flag, created_at, updated_at) "
        "VALUES ('chart-src', 'https://charts.example.com/index.yaml', 4, now(), now())"
    )


# ── Module fixture: throwaway PG database, upgraded to pre-phase-3 + seeded ─


@pytest.fixture(scope="module")
def mig_env():
    async def _create_db(conn):
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        await conn.execute(f"CREATE DATABASE {TEST_DB}")

    async def _drop_db(conn):
        await conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")

    try:
        asyncio.run(_with_admin(_create_db))
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"PostgreSQL not available for the migration test: {exc}")

    mp = pytest.MonkeyPatch()
    # WHY: alembic/env.py overrides sqlalchemy.url from app settings, so the
    # test database must be injected through the settings singleton.
    mp.setattr(settings, "database_url", TEST_URL, raising=True)
    try:
        cfg = _alembic_config()
        command.upgrade(cfg, PRE_ENUM_SPLIT)
        command.upgrade(cfg, PRE_PHASE3)

        async def _seed_wrapper():
            conn = await _connect_test_db()
            try:
                await _seed(conn)
            finally:
                await conn.close()

        asyncio.run(_seed_wrapper())
        yield cfg
    finally:
        mp.undo()
        asyncio.run(_with_admin(_drop_db))


# ── Queries ─────────────────────────────────────────────────────────────────


def _fetch_all(query: str, *args) -> list[dict]:
    async def _q():
        conn = await _connect_test_db()
        try:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    return asyncio.run(_q())


def _fetch_one(query: str, *args) -> dict | None:
    rows = _fetch_all(query, *args)
    return rows[0] if rows else None


def _providers() -> dict[str, dict]:
    """Map provider name → row for the migrated providers."""
    rows = _fetch_all("SELECT * FROM resource_providers ORDER BY id")
    return {r["name"]: r for r in rows}


def _columns(table: str) -> set[str]:
    rows = _fetch_all(
        "SELECT column_name FROM information_schema.columns WHERE table_name = $1",
        table,
    )
    return {r["column_name"] for r in rows}


# ── Tests (ordered: each step continues the previous state) ────────────────


class TestProvidersMigrationStage14:
    def test_upgrade_transfers_all_legacy_rows(self, mig_env):
        """Phase-3 upgrade migrates 6 legacy tables → 10 providers, no loss."""
        command.upgrade(mig_env, PHASE3)

        providers = _providers()
        assert len(providers) == 10, "expected 10 migrated provider rows"
        expected_names = {
            "legacy-source-1",
            "legacy-source-2",
            "legacy-gitlab-platform-gitlab",
            "legacy-gitlab-ext-gitlab",
            "legacy-github-my-github",
            "legacy-harbor-platform-harbor",
            "legacy-docker-target-registry",
            "legacy-docker-dockerhub-private",
            "legacy-helm-private-charts",
            "legacy-helm-public-charts",
        }
        assert set(providers) == expected_names

        p = providers

        # gitlab default instance → system/internal/protected (11.3.4)
        sys_gitlab = p["legacy-gitlab-platform-gitlab"]
        assert sys_gitlab["subtype"] == "gitlab"
        assert sys_gitlab["category"] == "system"
        assert sys_gitlab["direction"] == "internal"
        assert sys_gitlab["visibility"] == "owner"
        assert sys_gitlab["is_protected"] is True
        assert sys_gitlab["is_default"] is True
        assert sys_gitlab["base_url"] == "http://gitlab.local"
        assert json.loads(sys_gitlab["config"]) == {"default_group_id": 42}
        assert sys_gitlab["credential_id"] is not None

        # gitlab non-default → private/external owned by the admin
        ext_gitlab = p["legacy-gitlab-ext-gitlab"]
        assert ext_gitlab["category"] == "private"
        assert ext_gitlab["direction"] == "external"
        assert ext_gitlab["owner_user_id"] is not None
        assert ext_gitlab["is_protected"] is False

        # github → private/external
        github = p["legacy-github-my-github"]
        assert github["subtype"] == "github"
        assert github["category"] == "private"
        assert github["direction"] == "external"

        # harbor → system/internal with default_project moved into config
        harbor = p["legacy-harbor-platform-harbor"]
        assert harbor["domain"] == "docker"
        assert harbor["subtype"] == "harbor"
        assert harbor["category"] == "system"
        assert harbor["direction"] == "internal"
        assert harbor["is_protected"] is True
        assert json.loads(harbor["config"]) == {"default_project": "default"}

        # docker registry used as target → system/internal, generic subtype
        target = p["legacy-docker-target-registry"]
        assert target["subtype"] == "generic_registry"
        assert target["category"] == "system"
        assert target["direction"] == "internal"
        assert json.loads(target["config"]) == {"api_style": "registry_v2"}

        # docker external registry → private/external docker_hub, priority kept
        dockerhub = p["legacy-docker-dockerhub-private"]
        assert dockerhub["subtype"] == "docker_hub"
        assert dockerhub["category"] == "private"
        assert dockerhub["direction"] == "external"
        assert dockerhub["priority"] == 5

        # helm: private when a secret exists, public otherwise
        assert p["legacy-helm-private-charts"]["category"] == "private"
        assert p["legacy-helm-public-charts"]["category"] == "public"
        assert p["legacy-helm-public-charts"]["credential_id"] is None

        # source_providers: anon builtin → public + protected; private keeps its
        # existing credential_id without duplication (11.1.3)
        anon = p["legacy-source-1"]
        assert anon["category"] == "public"
        assert anon["visibility"] == "public"
        assert anon["is_protected"] is True

        existing_cred = _fetch_one("SELECT id FROM credentials WHERE name = 'existing-cred'")
        assert existing_cred is not None
        assert p["legacy-source-2"]["credential_id"] == existing_cred["id"]

    def test_secret_ciphertext_copied_as_is(self, mig_env):
        """Fernet ciphertext is copied byte-for-byte; only the pre-Fernet
        fallback value gets encrypted (decrypted exactly once, in this test)."""
        pairs = [
            ("gitlab_instances", "token", "platform-gitlab", "legacy-gitlab-platform-gitlab"),
            ("gitlab_instances", "token", "ext-gitlab", "legacy-gitlab-ext-gitlab"),
            ("github_instances", "token", "my-github", "legacy-github-my-github"),
            ("harbor_instances", "password", "platform-harbor", "legacy-harbor-platform-harbor"),
            (
                "docker_registry_instances",
                "password",
                "target-registry",
                "legacy-docker-target-registry",
            ),
            (
                "helm_repository_instances",
                "password",
                "private-charts",
                "legacy-helm-private-charts",
            ),
        ]
        for table, column, instance_name, provider_name in pairs:
            legacy = _fetch_one(
                f"SELECT {column} AS secret FROM {table} WHERE name = $1", instance_name
            )
            provider = _fetch_one(
                "SELECT credential_id FROM resource_providers WHERE name = $1",
                provider_name,
            )
            stored = _fetch_one(
                "SELECT encrypted_secret FROM credentials WHERE id = $1",
                provider["credential_id"],
            )
            assert stored["encrypted_secret"] == legacy["secret"], (
                f"ciphertext bytes differ for {provider_name}"
            )

        # Fallback case: pre-Fernet plaintext is encrypted (never stored as-is).
        provider = _fetch_one(
            "SELECT credential_id FROM resource_providers WHERE name = $1",
            "legacy-docker-dockerhub-private",
        )
        stored = _fetch_one(
            "SELECT encrypted_secret FROM credentials WHERE id = $1",
            provider["credential_id"],
        )
        assert stored["encrypted_secret"] != PLAINTEXT_FALLBACK
        assert FERNET.decrypt(stored["encrypted_secret"].encode()).decode() == (PLAINTEXT_FALLBACK)

        # 7 migrated credentials + 1 pre-existing one.
        counts = _fetch_one("SELECT count(*) AS n FROM credentials")
        assert counts["n"] == 8

    def test_fk_relink(self, mig_env):
        """Consumers point at resource_providers (pipelines, source_repositories,
        docker_image_sources incl. target_provider_id, helm_chart_sources)."""
        src_repo = _fetch_one(
            "SELECT sr.provider_id, rp.name AS provider_name "
            "FROM source_repositories sr "
            "LEFT JOIN resource_providers rp ON rp.id = sr.provider_id"
        )
        assert src_repo["provider_name"] == "legacy-source-2"

        pipeline = _fetch_one(
            "SELECT p.provider_id, rp.name AS provider_name, rp.category, rp.direction "
            "FROM pipelines p "
            "LEFT JOIN resource_providers rp ON rp.id = p.provider_id"
        )
        assert pipeline["provider_name"] == "legacy-gitlab-platform-gitlab"
        assert pipeline["category"] == "system"
        assert pipeline["direction"] == "internal"

        image_source = _fetch_one(
            "SELECT dis.provider_id, rp.name AS source_name, dis.target_provider_id, "
            "trp.name AS target_name "
            "FROM docker_image_sources dis "
            "LEFT JOIN resource_providers rp ON rp.id = dis.provider_id "
            "LEFT JOIN resource_providers trp ON trp.id = dis.target_provider_id"
        )
        assert image_source["source_name"] == "legacy-docker-target-registry"
        assert image_source["target_name"] == "legacy-docker-target-registry"

        chart_source = _fetch_one(
            "SELECT hcs.provider_id, rp.name AS provider_name, rp.domain, rp.direction "
            "FROM helm_chart_sources hcs "
            "LEFT JOIN resource_providers rp ON rp.id = hcs.provider_id"
        )
        assert chart_source["provider_name"] == "legacy-helm-private-charts"
        assert chart_source["domain"] == "helm"
        assert chart_source["direction"] == "external"

    def test_migrate_data_is_idempotent(self, mig_env):
        """A second execution of the data-migration step creates no duplicates."""
        mod = _load_migration_module()
        before_providers = _fetch_one("SELECT count(*) AS n FROM resource_providers")["n"]
        before_credentials = _fetch_one("SELECT count(*) AS n FROM credentials")["n"]

        class _StubOp:
            def __init__(self, conn):
                self._conn = conn

            def get_bind(self):
                return self._conn

        original_op = mod.op

        def _rerun(sync_conn) -> None:
            mod.op = _StubOp(sync_conn)
            try:
                mod._migrate_data()
            finally:
                mod.op = original_op

        async def _run_on_engine():
            engine = create_async_engine(TEST_URL)
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(_rerun)
            finally:
                await engine.dispose()

        asyncio.run(_run_on_engine())

        after_providers = _fetch_one("SELECT count(*) AS n FROM resource_providers")["n"]
        after_credentials = _fetch_one("SELECT count(*) AS n FROM credentials")["n"]
        assert after_providers == before_providers
        assert after_credentials == before_credentials

        dupes = _fetch_all(
            "SELECT name, count(*) AS n FROM resource_providers GROUP BY name HAVING count(*) > 1"
        )
        assert dupes == []

    def test_downgrade_then_reupgrade(self, mig_env):
        """Downgrade removes migrated rows and relink columns; a subsequent
        upgrade runs cleanly (full cycle is repeatable)."""
        command.downgrade(mig_env, "-1")

        providers = _fetch_all("SELECT * FROM resource_providers")
        assert providers == [], "downgrade must remove all migrated providers"

        migrated_creds = _fetch_all("SELECT * FROM credentials WHERE name LIKE 'migrated-%'")
        assert migrated_creds == []
        # Pre-existing credential survives the downgrade.
        assert _fetch_one("SELECT id FROM credentials WHERE name = 'existing-cred'")

        # Relink columns are gone; legacy columns untouched.
        for table in [
            "source_repositories",
            "pipelines",
            "docker_image_sources",
            "helm_chart_sources",
        ]:
            assert "provider_id" not in _columns(table)
        assert "target_provider_id" not in _columns("docker_image_sources")
        assert "source_provider_id" in _columns("source_repositories")
        assert "gitlab_instance_id" in _columns("pipelines")
        assert "registry_instance_id" in _columns("docker_image_sources")

        # Legacy tables still hold their original rows (read-through preserved).
        assert _fetch_one("SELECT count(*) AS n FROM gitlab_instances")["n"] == 2
        assert _fetch_one("SELECT count(*) AS n FROM source_providers")["n"] == 2
        assert _fetch_one("SELECT count(*) AS n FROM docker_registry_instances")["n"] == 2

        # Re-run: upgrade → downgrade cycle is repeatable without errors.
        command.upgrade(mig_env, PHASE3)
        assert _fetch_one("SELECT count(*) AS n FROM resource_providers")["n"] == 10
        command.downgrade(mig_env, "-1")
        assert _fetch_one("SELECT count(*) AS n FROM resource_providers")["n"] == 0
        command.upgrade(mig_env, PHASE3)
        assert _fetch_one("SELECT count(*) AS n FROM resource_providers")["n"] == 10
