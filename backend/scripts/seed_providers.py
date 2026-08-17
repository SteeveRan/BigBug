#!/usr/bin/env python3
"""
Idempotent default public provider seeder (Providers V3, phase 0).

Creates the four public "anonymous" providers from ``plans/features/providers-unified.md``
section 5.2 and is safe to run repeatedly: it upserts by ``name`` (UNIQUE among live rows),
only touching the *seeded* fields (``label``, ``is_default``, ``is_protected``) so that any
operator/owner customisations on the other columns are preserved.

Additionally seeds a Harbor *system* provider when ``HARBOR_URL`` is set. System providers
carry secrets and environment-specific URLs, so they are gated behind that env var and
created idempotently (upsert by ``name``), rotating the credential from the environment on
every run.

Run (from ``backend/``)::

    python -m scripts.seed_providers            # apply changes
    python -m scripts.seed_providers --dry-run  # print plan only, write nothing
"""

import argparse
import asyncio
import logging
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import decrypt_secret, encrypt_secret
from app.database import AsyncSessionLocal
from app.models.credential import Credential, CredentialType
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

HARBOR_SYSTEM_CREDENTIAL_NAME = "harbor-system-credential"
HARBOR_SYSTEM_PROVIDER_NAME = "harbor-system"

GITLAB_SYSTEM_CREDENTIAL_NAME = "gitlab-system-credential"
GITLAB_SYSTEM_PROVIDER_NAME = "gitlab-system"


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


def _harbor_env() -> dict | None:
    """Return the Harbor system-provider env config, or ``None`` when not set."""
    harbor_url = os.environ.get("HARBOR_URL", "").strip()
    if not harbor_url:
        return None
    projects = os.environ.get("HARBOR_PROJECTS_ALLOWLIST", "").strip()
    return {
        "base_url": harbor_url.rstrip("/"),
        "username": os.environ.get("HARBOR_USERNAME", ""),
        "password": os.environ.get("HARBOR_PASSWORD", ""),
        "default_project": os.environ.get("HARBOR_DEFAULT_PROJECT", "library"),
        "verify_ssl": os.environ.get("HARBOR_VERIFY_SSL", "true").lower()
        not in ("false", "0", "no", "off"),
        "projects_allowlist": [p.strip() for p in projects.split(",") if p.strip()],
    }


def _gitlab_env() -> dict | None:
    """Return the GitLab system-provider env config, or ``None`` when not set."""
    gitlab_url = os.environ.get("GITLAB_URL", "").strip()
    token = os.environ.get("GITLAB_TOKEN", "").strip()
    if not gitlab_url or not token:
        return None
    return {
        "base_url": gitlab_url.rstrip("/"),
        "username": os.environ.get("GITLAB_USERNAME", "root").strip() or "root",
        "token": token,
    }


async def _seed_system_gitlab(session: AsyncSession, *, dry_run: bool) -> list[dict]:
    """Upsert the GitLab system credential + provider (env-gated).

    The platform's own GitLab is the only provider allowed to trigger pipelines
    (providers-unified 11.3.4): domain=git, subtype=gitlab, category=system,
    direction=internal. Like the Harbor system provider, it is created
    idempotently (upsert by name) and rotates the credential from env.
    """
    env = _gitlab_env()
    if env is None:
        logger.info("GITLAB_URL/GITLAB_TOKEN not set — skipping system GitLab provider")
        return []

    actions: list[dict] = []

    # ── Credential (upsert by name) ──────────────────────────────────────
    cred_result = await session.execute(
        select(Credential).where(Credential.name == GITLAB_SYSTEM_CREDENTIAL_NAME)
    )
    credential = cred_result.scalar_one_or_none()
    encrypted = encrypt_secret(env["token"])

    if credential is None:
        actions.append({"action": "create", "name": GITLAB_SYSTEM_CREDENTIAL_NAME})
        if not dry_run:
            credential = Credential(
                name=GITLAB_SYSTEM_CREDENTIAL_NAME,
                credential_type=CredentialType.gitlab_token,
                provider="gitlab",
                username=env["username"],
                encrypted_secret=encrypted,
                base_url=env["base_url"],
            )
            session.add(credential)
            await session.flush()
    else:
        changed = []
        if credential.username != env["username"]:
            credential.username = env["username"]
            changed.append("username")
        if credential.base_url != env["base_url"]:
            credential.base_url = env["base_url"]
            changed.append("base_url")
        # Compare plaintext (Fernet tokens embed a timestamp, so ciphertext
        # differs per call even for identical secrets).
        current_plain = decrypt_secret(credential.encrypted_secret)
        if current_plain != env["token"]:
            credential.encrypted_secret = encrypted
            changed.append("encrypted_secret")
        if changed:
            actions.append(
                {
                    "action": "update",
                    "name": GITLAB_SYSTEM_CREDENTIAL_NAME,
                    "fields": sorted(changed),
                }
            )

    # ── Provider (upsert by name) ────────────────────────────────────────
    prov_result = await session.execute(
        select(ResourceProvider).where(
            ResourceProvider.name == GITLAB_SYSTEM_PROVIDER_NAME,
            ResourceProvider.is_deleted.is_(False),
        )
    )
    provider = prov_result.scalar_one_or_none()

    if provider is None:
        actions.append({"action": "create", "name": GITLAB_SYSTEM_PROVIDER_NAME})
        if not dry_run:
            session.add(
                ResourceProvider(
                    domain=ProviderDomain.git,
                    subtype=ProviderSubtype.gitlab,
                    category=ProviderCategory.system,
                    visibility=ProviderVisibility.owner,
                    direction=ProviderDirection.internal,
                    name=GITLAB_SYSTEM_PROVIDER_NAME,
                    label="GitLab (system)",
                    base_url=env["base_url"],
                    credential_id=credential.id,
                    config={"api_version": "v4"},
                    is_protected=True,
                    is_default=True,
                    verify_ssl=True,
                )
            )
    else:
        changed = []
        if provider.label != "GitLab (system)":
            provider.label = "GitLab (system)"
            changed.append("label")
        if provider.base_url != env["base_url"]:
            provider.base_url = env["base_url"]
            changed.append("base_url")
        if provider.credential_id != credential.id:
            provider.credential_id = credential.id
            changed.append("credential_id")
        if provider.is_protected is not True:
            provider.is_protected = True
            changed.append("is_protected")
        if provider.is_default is not True:
            provider.is_default = True
            changed.append("is_default")
        if changed:
            actions.append(
                {
                    "action": "update",
                    "name": GITLAB_SYSTEM_PROVIDER_NAME,
                    "fields": sorted(changed),
                }
            )

    if not actions:
        logger.info("System GitLab provider is up to date — nothing to do.")
    return actions


async def _seed_system_harbor(session: AsyncSession, *, dry_run: bool) -> list[dict]:
    """Upsert the Harbor system credential + provider (env-gated).

    The seed owns ``label/is_default/is_protected/base_url/config/verify_ssl/
    credential_id`` for the system provider and rotates the credential from env
    on every run, unlike the public section which only touches label/default/
    protected.
    """
    env = _harbor_env()
    if env is None:
        logger.info("HARBOR_URL not set — skipping system Harbor provider")
        return []

    actions: list[dict] = []

    # ── Credential (upsert by name) ──────────────────────────────────────
    cred_result = await session.execute(
        select(Credential).where(Credential.name == HARBOR_SYSTEM_CREDENTIAL_NAME)
    )
    credential = cred_result.scalar_one_or_none()
    encrypted = encrypt_secret(env["password"]) if env["password"] else None

    if credential is None:
        actions.append({"action": "create", "name": HARBOR_SYSTEM_CREDENTIAL_NAME})
        if not dry_run:
            credential = Credential(
                name=HARBOR_SYSTEM_CREDENTIAL_NAME,
                credential_type=CredentialType.https_basic,
                provider="harbor",
                username=env["username"],
                encrypted_secret=encrypted,
                base_url=env["base_url"],
            )
            session.add(credential)
            await session.flush()
    else:
        changed = []
        if credential.username != env["username"]:
            credential.username = env["username"]
            changed.append("username")
        if credential.base_url != env["base_url"]:
            credential.base_url = env["base_url"]
            changed.append("base_url")
        # Compare plaintext, not ciphertext: Fernet tokens embed a timestamp so
        # encrypt_secret() returns a different token on every call. Comparing
        # ciphertext would force a spurious credential rotation each run.
        current_plain = decrypt_secret(credential.encrypted_secret)
        new_plain = env["password"] or None
        if current_plain != new_plain:
            credential.encrypted_secret = encrypted
            changed.append("encrypted_secret")
        if changed:
            actions.append(
                {"action": "update", "name": HARBOR_SYSTEM_CREDENTIAL_NAME, "fields": sorted(changed)}
            )

    # ── Provider (upsert by name) ────────────────────────────────────────
    prov_result = await session.execute(
        select(ResourceProvider).where(
            ResourceProvider.name == HARBOR_SYSTEM_PROVIDER_NAME,
            ResourceProvider.is_deleted.is_(False),
        )
    )
    provider = prov_result.scalar_one_or_none()

    config = {
        "default_project": env["default_project"],
        "robot_prefix": "robot$",
        "projects_allowlist": env["projects_allowlist"],
    }

    if provider is None:
        actions.append({"action": "create", "name": HARBOR_SYSTEM_PROVIDER_NAME})
        if not dry_run:
            session.add(
                ResourceProvider(
                    domain=ProviderDomain.docker,
                    subtype=ProviderSubtype.harbor,
                    category=ProviderCategory.system,
                    visibility=ProviderVisibility.public,
                    direction=ProviderDirection.internal,
                    name=HARBOR_SYSTEM_PROVIDER_NAME,
                    label="Harbor (system)",
                    base_url=env["base_url"],
                    credential_id=credential.id,
                    config=config,
                    is_protected=True,
                    is_default=True,
                    verify_ssl=env["verify_ssl"],
                )
            )
    else:
        changed = []
        if provider.label != "Harbor (system)":
            provider.label = "Harbor (system)"
            changed.append("label")
        if provider.base_url != env["base_url"]:
            provider.base_url = env["base_url"]
            changed.append("base_url")
        if provider.config != config:
            provider.config = config
            changed.append("config")
        if provider.credential_id != credential.id:
            provider.credential_id = credential.id
            changed.append("credential_id")
        if provider.verify_ssl is not env["verify_ssl"]:
            provider.verify_ssl = env["verify_ssl"]
            changed.append("verify_ssl")
        if provider.is_protected is not True:
            provider.is_protected = True
            changed.append("is_protected")
        if provider.is_default is not True:
            provider.is_default = True
            changed.append("is_default")
        if changed:
            actions.append(
                {"action": "update", "name": HARBOR_SYSTEM_PROVIDER_NAME, "fields": sorted(changed)}
            )

    if not actions:
        logger.info("System Harbor provider is up to date — nothing to do.")
    return actions


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

    actions.extend(await _seed_system_harbor(session, dry_run=dry_run))
    actions.extend(await _seed_system_gitlab(session, dry_run=dry_run))

    if dry_run:
        await session.rollback()
    else:
        await session.commit()
    return actions


def _log_actions(actions: list[dict], *, dry_run: bool) -> None:
    if not actions:
        logger.info("Providers are up to date — nothing to do.")
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
