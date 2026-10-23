"""
@file e2e/conftest.py
@description E2E fixtures against a live dev backend over real HTTP. No sqlite,
              no ``Base.metadata.create_all``, no dependency overrides and no
              monkeypatching of ``app.core.secrets`` — every interaction goes
              through the running dev stand (kind, https://api.local).
@dependencies httpx, pytest, pytest-asyncio, backend/tests/e2e/openapi_utils.py
@relatedFiles ./openapi_utils.py, ../../scripts/test-e2e.sh, ../../scripts/seed_e2e.py
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from httpx import AsyncHTTPTransport

from scripts.seed_e2e import (
    E2E_ADMIN_PASSWORD as ADMIN_PASSWORD,
)
from scripts.seed_e2e import (
    E2E_ADMIN_USERNAME as ADMIN_USERNAME,
)
from scripts.seed_e2e import (
    E2E_OPERATOR_PASSWORD,
    E2E_OPERATOR_USERNAME,
    E2E_VIEWER_PASSWORD,
    E2E_VIEWER_USERNAME,
)
from tests.e2e.openapi_utils import (
    CALLED_OPERATIONS,
    assert_matches_openapi,
    load_openapi_spec,
    write_endpoint_report,
)

__all__ = [
    "BASE_URL",
    "assert_matches_openapi",
    "admin_headers",
    "viewer_headers",
    "unique_prefix",
    "unique_name",
    "openapi_spec",
]

# ──────────────────────────────────────────────────────────────────────────
# Base URL / environment
# ──────────────────────────────────────────────────────────────────────────

BASE_URL = os.environ.get("BIGBUG_E2E_BASE_URL", "https://api.local").rstrip("/")

# E2E accounts are provisioned by scripts/seed-e2e.sh (ADR-0024 §3) before the
# run; credentials are shared constants from scripts/seed_e2e.py — no env-provided
# admin credentials (ADR-0024 policy: no real credentials in e2e).


def _auth(token: str) -> dict[str, str]:
    """Authorization header for a JWT access token."""
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────────────────
# Server availability (session-scoped, fail-fast with a useful message)
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _server_available() -> Iterator[None]:
    """Fail fast with a clear message when the dev backend is not reachable."""
    try:
        resp = httpx.get(f"{BASE_URL}/api/health", timeout=5.0)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — wrap any connectivity failure
        pytest.exit(
            f"E2E backend is not reachable at {BASE_URL} ({exc}). "
            "Start the dev stand first: make infra-init (+ helm upgrade bigbug). "
            "TLS error? Run infrastructure/kind/certs.sh (ADR-0030 §3) — "
            "test-e2e.sh sets SSL_CERT_FILE automatically.",
            returncode=1,
        )
    yield


@pytest.fixture(scope="session")
def openapi_spec() -> dict[str, Any]:
    """The frozen OpenAPI contract, loaded once for the whole e2e session."""
    return load_openapi_spec()


# ──────────────────────────────────────────────────────────────────────────
# HTTP client (real network I/O)
# ──────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Async HTTP client pointed at the live backend (no ASGITransport).

    The transport is created *per test*: pytest-asyncio runs every test in its
    own event loop, and a module-level shared ``AsyncHTTPTransport`` would pin
    its connection pool to the first loop, hanging later tests' requests.
    ``retries=3`` also makes the suite robust against ``uvicorn --reload``
    restarts that drop in-flight requests during development.
    """
    transport = AsyncHTTPTransport(retries=3)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0, transport=transport) as ac:
        yield ac


# ──────────────────────────────────────────────────────────────────────────
# Authentication fixtures
#
# Tokens are session-scoped SYNC fixtures (only 3 logins per run, well under
# the 5/min rate limit). A sync ``httpx.Client`` is used so the token fixtures
# do not depend on pytest-asyncio's per-test event loop, which would break
# session-scoped async fixtures.
# ──────────────────────────────────────────────────────────────────────────


def _login_sync(username: str, password: str) -> str:
    """Perform a synchronous login and return the access token.

    Uses a unique ``X-Forwarded-For`` so the login rate limit (5/min per
    client identity) never trips across the few logins in an e2e session.
    """
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        resp = c.post(
            "/api/auth/login",
            json={"username": username, "password": password},
            headers={"X-Forwarded-For": f"10.0.0.{uuid.uuid4().hex[:6]}"},
        )
        assert resp.status_code == 200, (
            f"Login failed for '{username}' ({resp.status_code}): {resp.text}"
        )
        return resp.json()["access_token"]


@pytest.fixture(scope="session")
def admin_token() -> str:
    """Access token for the seeded e2e-admin account (scripts/seed_e2e.py)."""
    return _login_sync(ADMIN_USERNAME, ADMIN_PASSWORD)


@pytest.fixture
def admin_headers(admin_token: str) -> dict[str, str]:
    """Authorization headers for the admin user."""
    return _auth(admin_token)


@pytest.fixture(scope="session")
def viewer_token(admin_token: str) -> str:
    """Access token for the seeded viewer account (scripts/seed-e2e.sh).

    The seed creates stable e2e-viewer/e2e-operator accounts; the token is
    refreshed per session (no user teardown — accounts are idempotent).
    """
    return _login_sync(E2E_VIEWER_USERNAME, E2E_VIEWER_PASSWORD)


@pytest.fixture
def viewer_headers(viewer_token: str) -> dict[str, str]:
    """Authorization headers for the least-privileged viewer user."""
    return _auth(viewer_token)


@pytest.fixture(scope="session")
def operator_token(admin_token: str) -> str:
    """Access token for the seeded operator account (scripts/seed-e2e.sh)."""
    return _login_sync(E2E_OPERATOR_USERNAME, E2E_OPERATOR_PASSWORD)


@pytest.fixture
def operator_headers(operator_token: str) -> dict[str, str]:
    """Authorization headers for the operator user."""
    return _auth(operator_token)


# ──────────────────────────────────────────────────────────────────────────
# Data-isolation helper: unique names + teardown
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture
def unique_prefix() -> str:
    """A short unique prefix for entity names so e2e runs never collide."""
    return f"e2e-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def unique_name(unique_prefix: str) -> str:
    """A single unique name for a test entity."""
    return unique_prefix


# ──────────────────────────────────────────────────────────────────────────
# Endpoint-coverage report (session teardown)
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session", autouse=True)
def _endpoint_report(openapi_spec: dict[str, Any]) -> Iterator[None]:
    """Reset the collector and write the endpoint-coverage report at teardown."""
    CALLED_OPERATIONS.clear()
    yield
    write_endpoint_report(openapi_spec)


@pytest.fixture(scope="session", autouse=True)
def _warm_tokens(
    admin_token: str,
    viewer_token: str,
    operator_token: str,
) -> None:
    """Eagerly resolve all session-scoped auth tokens before any test runs.

    The session-scoped token fixtures are *sync* (they use ``httpx.Client``).
    If left lazy, their first use happens inside an async test — interleaving a
    synchronous network call with pytest-asyncio's running loop, which can
    corrupt the loop and deadlock later requests (surfacing as a 30s
    ``httpx.ReadTimeout``). Resolving them up-front keeps every sync login
    before the first per-test event loop exists.
    """
    del admin_token, viewer_token, operator_token
