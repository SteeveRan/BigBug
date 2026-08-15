#!/usr/bin/env python3
"""
Idempotent default public provider seeder (Providers V3, phase 0).

Creates the four public "anonymous" providers from ``plans/features/providers-unified.md``
section 5.2 and is safe to run repeatedly: it upserts by ``name`` (UNIQUE among live rows),
only touching the *seeded* fields (``label``, ``is_default``, ``is_protected``) so that any
operator/owner customisations on the other columns are preserved.

System providers (the platform GitLab, Harbor) are intentionally NOT created here — they
carry secrets / environment-specific URLs and are configured manually by an administrator.

Run (from ``backend/``)::

    python -m scripts.seed_providers            # apply changes
    python -m scripts.seed_providers --dry-run  # print plan only, write nothing
"""

import argparse
import asyncio
import logging
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ProviderVisibility,
    ResourceProvider,
)

logger = logging.getLogger("seed_providers")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [seed_providers] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
    stream=sys.stderr,
)

# ── Seeded defaults (section 5.2) ────────────────────────────────────────
# All entries are public (visibility=public), external, protected and the
# default for their (domain, subtype, category, direction) scope.
DEFAULT_PROVIDERS: tuple[dict, ...] = (
    {
        "name": "github-anonymous",
        "label": "GitHub (anonymous)",
        "domain": ProviderDomain.git,
        "subtype": ProviderSubtype.github,
        "category": ProviderCategory.public,
        "direction": ProviderDirection.external,
        "base_url": "https://api.github.com",
    },
    {
        "name": "gitlab-anonymous",
        "label": "GitLab (anonymous)",
        "domain": ProviderDomain.git,
        "subtype": ProviderSubtype.gitlab,
        "category": ProviderCategory.public,
        "direction": ProviderDirection.external,
        "base_url": "https://gitlab.com",
    },
    {
        "name": "generic-anonymous",
        "label": "Generic Git (anonymous)",
        "domain": ProviderDomain.git,
        "subtype": ProviderSubtype.generic_git,
        "category": ProviderCategory.public,
        "direction": ProviderDirection.external,
        "base_url": None,
    },
    {
        "name": "dockerhub-anonymous",
        "label": "Docker Hub (anonymous)",
        "domain": ProviderDomain.docker,
        "subtype": ProviderSubtype.docker_hub,
        "category": ProviderCategory.public,
        "direction": ProviderDirection.external,
        "base_url": "https://registry-1.docker.io",
    },
)


def _seeded_updates(spec: dict, existing: ResourceProvider) -> dict:
    """Return the seeded-field values that differ from *existing*.

    Only ``label``, ``is_default`` and ``is_protected`` are owned by the seed;
    everything else (config, base_url, credential_id, owner, …) is preserved.
    """
    updates: dict = {}
    if existing.label != spec["label"]:
        updates["label"] = spec["label"]
    if existing.is_default is not True:
        updates["is_default"] = True
    if existing.is_protected is not True:
        updates["is_protected"] = True
    return updates


async def seed_providers(session: AsyncSession, *, dry_run: bool = False) -> list[dict]:
    """Upsert the default providers into *session*.

    Returns an ordered list of planned/applied changes. In ``dry_run`` mode no
    rows are written and the session is rolled back so nothing leaks out.
    """
    actions: list[dict] = []

    for spec in DEFAULT_PROVIDERS:
        result = await session.execute(
            select(ResourceProvider).where(
                ResourceProvider.name == spec["name"],
                ResourceProvider.is_deleted.is_(False),
            )
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            actions.append({"action": "create", "name": spec["name"]})
            if not dry_run:
                session.add(
                    ResourceProvider(
                        domain=spec["domain"],
                        subtype=spec["subtype"],
                        category=spec["category"],
                        visibility=ProviderVisibility.public,
                        direction=spec["direction"],
                        name=spec["name"],
                        label=spec["label"],
                        base_url=spec["base_url"],
                        config={},
                        is_protected=True,
                        is_default=True,
                    )
                )
            continue

        updates = _seeded_updates(spec, existing)
        if updates:
            actions.append(
                {"action": "update", "name": spec["name"], "fields": sorted(updates)}
            )
            if not dry_run:
                for field, value in updates.items():
                    setattr(existing, field, value)

    if dry_run:
        await session.rollback()
    else:
        await session.commit()
    return actions


def _log_actions(actions: list[dict], *, dry_run: bool) -> None:
    if not actions:
        logger.info("Default providers are up to date — nothing to do.")
        return

    for action in actions:
        if action["action"] == "create":
            logger.info("[%s] create %s", "plan" if dry_run else "apply", action["name"])
        else:
            logger.info(
                "[%s] update %s: %s",
                "plan" if dry_run else "apply",
                action["name"],
                ", ".join(action["fields"]),
            )

    if dry_run:
        logger.info("DRY RUN — no changes written.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed default public providers.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the change plan without writing anything",
    )
    args = parser.parse_args(argv)

    async def _run() -> list[dict]:
        async with AsyncSessionLocal() as session:
            return await seed_providers(session, dry_run=args.dry_run)

    try:
        actions = asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — surface as a non-zero exit
        logger.error("Provider seeding failed: %s", exc)
        return 1

    _log_actions(actions, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
