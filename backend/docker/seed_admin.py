#!/usr/bin/env python3
"""
Idempotent admin user seeder.

Reads credentials from environment variables (with sensible defaults)
and creates an admin user IFF no user with the ``admin`` role exists yet.

Environment variables
---------------------
ADMIN_USERNAME : str, default ``"admin"``
    Username for the initial administrator account.
ADMIN_EMAIL : str, default ``"admin@bigbug.local"``
    Email for the initial administrator account.
ADMIN_PASSWORD : str, default ``"admin"``
    Password for the initial administrator account.

Exit codes
----------
0  – admin already exists, or was created successfully
1  – database connection or query error
2  – existing user with the same username/email but different role
"""

import asyncio
import logging
import os
import sys

from sqlalchemy import select

from app.core.security import get_password_hash
from app.database import AsyncSessionLocal
from app.models.role import Role, UserRole
from app.models.user import User

logger = logging.getLogger("seed_admin")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [seed_admin] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    stream=sys.stderr,
)


def _env(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value if value else default


async def _seed() -> int:
    username = _env("ADMIN_USERNAME", "admin")
    email = _env("ADMIN_EMAIL", "admin@bigbug.local")
    password = _env("ADMIN_PASSWORD", "admin")

    async with AsyncSessionLocal() as session:
        # ── Check whether any admin already exists ──────────────────────
        stmt = (
            select(User)
            .join(User.user_roles)
            .join(UserRole.role)
            .where(Role.name == "admin", User.is_active.is_(True))
        )
        result = await session.execute(stmt)
        existing_admin = result.scalar_one_or_none()

        if existing_admin is not None:
            logger.info(
                "Admin user already exists (id=%s, username=%s) — nothing to seed.",
                existing_admin.id,
                existing_admin.username,
            )
            return 0

        # ── Ensure the admin role exists (created by Alembic migrations,
        #     but defensive check in case this script is run before them) ──
        role_result = await session.execute(select(Role).where(Role.name == "admin"))
        admin_role = role_result.scalar_one_or_none()

        if admin_role is None:
            logger.error(
                "The 'admin' role does not exist in the database. "
                "Did you run `alembic upgrade head`?"
            )
            return 1

        # ── Check for username/email conflicts ──────────────────────────
        conflict = await session.execute(
            select(User).where((User.username == username) | (User.email == email))
        )
        conflicting = conflict.scalars().all()
        if conflicting:
            logger.error(
                "Cannot seed admin: existing user(s) with the same username "
                "(%s) or email (%s) but not assigned the admin role. "
                "Resolve the conflict manually.",
                {u.username for u in conflicting},
                {u.email for u in conflicting},
            )
            return 2

        # ── Create the admin user ───────────────────────────────────────
        user = User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            is_active=True,
        )
        session.add(user)
        await session.flush()

        session.add(UserRole(user_id=user.id, role_id=admin_role.id))
        await session.commit()

        logger.info(
            "Admin user seeded (id=%s, username=%s, email=%s).",
            user.id,
            user.username,
            user.email,
        )
        return 0


def main() -> int:
    return asyncio.run(_seed())


if __name__ == "__main__":
    sys.exit(main())
