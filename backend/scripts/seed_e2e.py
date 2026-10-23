#!/usr/bin/env python3
"""
Idempotent e2e account seeder (ADR-0024 §3, ADR-0018).

Creates/updates the dedicated e2e users in the BigBug DB (local email/password
auth). Passwords are test constants, NOT secrets (ADR-0024 policy: no real
credentials in e2e). Called by ``scripts/seed-e2e.sh`` before every e2e run;
also usable directly::

    python -m scripts.seed_e2e          # from backend/

Accounts (username / password / role):
    e2e-admin    / e2e-admin-password    / admin
    e2e-viewer   / e2e-viewer-password   / viewer
    e2e-operator / e2e-operator-password / operator

The SSO realm user (``bigbug``/``bigbug``) is NOT created here — realm users
are provisioned by tofu (``infra-apps/modules/keycloak_conf/users.tf``) so they
are recreated by ``tofu apply`` together with the stand.
"""

import asyncio
import logging
import sys

from sqlalchemy import delete, select

from app.core.security import get_password_hash, verify_password
from app.database import AsyncSessionLocal
from app.models.role import Role, UserRole
from app.models.user import User

# ── Shared e2e constants (imported by tests/e2e/conftest.py) ──────────────

E2E_ADMIN_USERNAME = "e2e-admin"
E2E_ADMIN_PASSWORD = "e2e-admin-password"
E2E_VIEWER_USERNAME = "e2e-viewer"
E2E_VIEWER_PASSWORD = "e2e-viewer-password"
E2E_OPERATOR_USERNAME = "e2e-operator"
E2E_OPERATOR_PASSWORD = "e2e-operator-password"

E2E_ACCOUNTS: tuple[dict[str, str], ...] = (
    {"username": E2E_ADMIN_USERNAME, "password": E2E_ADMIN_PASSWORD, "role": "admin"},
    {"username": E2E_VIEWER_USERNAME, "password": E2E_VIEWER_PASSWORD, "role": "viewer"},
    {"username": E2E_OPERATOR_USERNAME, "password": E2E_OPERATOR_PASSWORD, "role": "operator"},
)

logger = logging.getLogger("seed_e2e")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [seed_e2e] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    stream=sys.stderr,
)


async def seed_e2e_users(session) -> list[str]:
    """Upsert the e2e accounts into *session*; returns applied action names."""
    actions: list[str] = []

    for spec in E2E_ACCOUNTS:
        result = await session.execute(select(User).where(User.username == spec["username"]))
        user = result.scalar_one_or_none()

        role_result = await session.execute(select(Role).where(Role.name == spec["role"]))
        role = role_result.scalar_one_or_none()
        if role is None:
            raise RuntimeError(
                f"Role '{spec['role']}' does not exist — run `alembic upgrade head` first"
            )

        if user is None:
            user = User(
                username=spec["username"],
                email=f"{spec['username']}@bigbug.local",
                hashed_password=get_password_hash(spec["password"]),
                is_active=True,
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()
            actions.append(f"create {spec['username']}")
            continue

        # Idempotent update: rotate password if it drifted, re-activate,
        # reset roles to exactly the expected one.
        if not user.hashed_password or not verify_password(spec["password"], user.hashed_password):
            user.hashed_password = get_password_hash(spec["password"])
        user.is_active = True
        await session.execute(delete(UserRole).where(UserRole.user_id == user.id))
        session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.commit()
        actions.append(f"update {spec['username']}")

    return actions


def main() -> int:
    try:
        actions = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — surface as a non-zero exit
        logger.error("E2E account seeding failed: %s", exc)
        return 1

    for action in actions:
        logger.info("apply %s", action)
    logger.info("E2E accounts seeded.")
    return 0


async def _run() -> list[str]:
    async with AsyncSessionLocal() as session:
        return await seed_e2e_users(session)


if __name__ == "__main__":
    sys.exit(main())
