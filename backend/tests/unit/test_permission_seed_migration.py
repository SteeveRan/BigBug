"""
@file test_permission_seed_migration.py
@description Verifies that the consolidated RBAC seeding migration
             (``seed_initial_data``) actually writes the providers/teams/
             credentials permission rows into the ``permissions`` table and
             links them to the default roles.

             This is the regression test for the root-cause RBAC bug: those
             permission strings only existed in ``docker/seed_admin.py`` (Python
             lists) but no Alembic migration inserted them into the DB, so the
             admin's JWT never contained them and ``GET /api/providers`` returned
             403 while the Settings pages rendered empty (PermissionGate → null).

             After the Alembic reset the entire chain is two revisions
             (``initial schema`` → ``seed initial data``), so the test simply runs
             ``alembic upgrade head`` against a throwaway PostgreSQL database and
             then reads ``permissions`` / ``role_permissions`` directly. It is
             skipped when PostgreSQL is unavailable.
@dependencies alembic, asyncpg, backend/alembic/versions/*_seed_initial_data.py
"""

import asyncio
import os
from pathlib import Path

import asyncpg
import pytest
from alembic.config import Config as AlembicConfig

from alembic import command
from app.config import settings

# ── Test-environment constants ──────────────────────────────────────────────

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_DIR = BACKEND_DIR / "alembic"

PG_HOST_DSN = os.environ.get("BIGBUG_MIGTEST_PG", "bigbug:bigbug@localhost:5432")
TEST_DB = "bigbug_perms_test_pytest"
ADMIN_URL = f"postgresql://{PG_HOST_DSN}/postgres"
TEST_URL = f"postgresql+asyncpg://{PG_HOST_DSN}/{TEST_DB}"

# ── Canonical providers/teams/credentials permission subset expected after ──
# the consolidated seed (source: permissions.md section "Распределение по ролям").
EXPECTED_PERMISSIONS = frozenset(
    {
        "providers:read",
        "providers:write",
        "providers:delete",
        "providers:use",
        "providers:read_all",
        "providers_system:write",
        "providers:share",
        "teams:read",
        "teams:write",
        "teams:manage_members",
        "credentials:write",
    }
)


def _alembic_config() -> AlembicConfig:
    cfg = AlembicConfig()
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    return cfg


async def _with_admin(coro_fn):
    conn = await asyncpg.connect(ADMIN_URL)
    try:
        return await coro_fn(conn)
    finally:
        await conn.close()


async def _connect_test_db():
    return await asyncpg.connect(f"postgresql://{PG_HOST_DSN}/{TEST_DB}")


def _fetch_all(query: str, *args) -> list[dict]:
    async def _q():
        conn = await _connect_test_db()
        try:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]
        finally:
            await conn.close()

    return asyncio.run(_q())


# ── Module fixture: throwaway PG database upgraded to head ─────────────────


@pytest.fixture(scope="module")
def perm_env():
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
        command.upgrade(cfg, "head")
        yield cfg
    finally:
        mp.undo()
        asyncio.run(_with_admin(_drop_db))


# ── Tests ───────────────────────────────────────────────────────────────────


class TestPermissionSeedMigration:
    def test_permissions_table_contains_providers_teams_credentials(self, perm_env):
        """The consolidated seed inserts every providers/teams/credentials permission row."""
        rows = _fetch_all("SELECT name FROM permissions")
        existing = {r["name"] for r in rows}
        missing = EXPECTED_PERMISSIONS - existing
        assert not missing, (
            f"Permissions missing from the migrated DB: {sorted(missing)}. "
            "The seeding migration (seed_initial_data) did not insert them."
        )

    def test_admin_role_linked_to_all_new_permissions(self, perm_env):
        """role_permissions links the admin role to all 11 new permissions."""
        rows = _fetch_all(
            "SELECT p.name "
            "FROM role_permissions rp "
            "JOIN roles r ON r.id = rp.role_id "
            "JOIN permissions p ON p.id = rp.permission_id "
            "WHERE r.name = 'admin'"
        )
        admin_permissions = {r["name"] for r in rows}
        missing = EXPECTED_PERMISSIONS - admin_permissions
        assert not missing, f"Admin role is missing these permission links: {sorted(missing)}"

    def test_operator_and_viewer_get_read_links(self, perm_env):
        """Operator and viewer both receive providers:read / teams:read (read-only)."""
        rows = _fetch_all(
            "SELECT r.name AS role, p.name AS permission "
            "FROM role_permissions rp "
            "JOIN roles r ON r.id = rp.role_id "
            "JOIN permissions p ON p.id = rp.permission_id "
            "WHERE r.name IN ('operator', 'viewer')"
        )
        by_role: dict[str, set[str]] = {"operator": set(), "viewer": set()}
        for row in rows:
            by_role[row["role"]].add(row["permission"])

        for role_name in ("operator", "viewer"):
            assert {"providers:read", "teams:read"} <= by_role[role_name], (
                f"{role_name} is missing read links: "
                f"{sorted({'providers:read', 'teams:read'} - by_role[role_name])}"
            )
