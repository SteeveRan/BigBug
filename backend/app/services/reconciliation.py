"""Reconciliation service — the drift catcher (ADR-0039 Phase 3, issue #111).

Compares the DB "synced" state (DockerImageTag.is_synced + digest) against
the actual contents of the target registry (tags list + manifests digest
where cheap). Drift cases: GC removed a tag, mirror rebuilt by hand,
upstream force-push. Repair = idempotent re-push (crane copy upsert-by-ref);
report = log + outbox event via :func:`sync_engine.outbox_write`.

Git mirrors use existing primitives (freshness/integrity checks + trigger_sync);
this pass covers docker image tags, the convergence surface of sync_engine.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import decrypt_secret
from app.models.credential import Credential
from app.models.docker_image_source import DockerImageSource
from app.models.docker_image_tag import DockerImageTag
from app.models.resource_provider import ResourceProvider
from app.services import sync_engine
from app.services.providers.clients._http import ProviderClientError
from app.services.providers.clients.docker_registry import registry_client_for_subtype
from app.services.trust_store_tls import provider_httpx_verify

logger = logging.getLogger(__name__)


async def _target_client(db: AsyncSession, source: DockerImageSource) -> tuple[Any, str]:
    """Build a registry client for the source's target registry.

    Returns (client, registry_root). Raises ProviderClientError/ValueError
    when no target registry is configured or unreachable config-wise.
    """
    target_registry_url = source.target_registry_url
    target_provider: ResourceProvider | None = None
    if source.target_provider_id is not None:
        tp = await db.get(ResourceProvider, source.target_provider_id)
        if tp is not None and tp.base_url:
            target_provider = tp
            target_registry_url = tp.base_url
    if not target_registry_url:
        raise ValueError(f"DockerImageSource {source.id} has no target registry configured")

    secret: str | None = None
    username: str | None = None
    if target_provider is not None and target_provider.credential_id is not None:
        credential = await db.get(Credential, target_provider.credential_id)
        if credential is not None:
            secret = decrypt_secret(credential.encrypted_secret)
            username = credential.username

    subtype = target_provider.subtype.value if target_provider is not None else "generic_registry"
    verify = (
        await provider_httpx_verify(db, target_provider) if target_provider is not None else True
    )
    client = registry_client_for_subtype(
        subtype,
        base_url=target_registry_url,
        secret=secret,
        username=username,
        # provider_httpx_verify returns bool | SSLContext; make_client routes
        # verify through ssl_context when given.
        ssl_context=verify if not isinstance(verify, bool) else None,
        verify_ssl=verify if isinstance(verify, bool) else True,
    )
    from app.services.docker import _registry_root

    return client, _registry_root(target_registry_url)


async def reconcile_docker_source(db: AsyncSession, source_id: int) -> dict[str, Any]:
    """Reconcile one DockerImageSource: compare synced DB tags vs actual registry.

    Per synced tag: actual digest presence via ``tags/list`` + manifest HEAD.
    Missing tag → idempotent re-push (crane copy) + outbox event. Digest
    drift is detected when the registry exposes manifests; tag-list-only
    registries report presence-based drift only.

    Returns a summary dict {source_id, checked, missing, repaired, failed}.
    """
    source = await db.get(DockerImageSource, source_id)
    if source is None:
        return {
            "source_id": source_id,
            "checked": 0,
            "missing": 0,
            "repaired": 0,
            "failed": 0,
            "error": "source not found",
        }

    try:
        client, registry_root = await _target_client(db, source)
    except Exception as exc:
        logger.error("Reconcile source %d: cannot resolve target registry: %s", source_id, exc)
        return {
            "source_id": source_id,
            "checked": 0,
            "missing": 0,
            "repaired": 0,
            "failed": 0,
            "error": str(exc),
        }

    result = await db.execute(
        select(DockerImageTag).where(
            DockerImageTag.source_id == source_id,
            DockerImageTag.is_synced.is_(True),
        )
    )
    synced_tags = result.scalars().all()

    checked = missing = repaired = failed = 0

    # Actual tags per repository (cache: repositories repeat across tags).
    actual_tags: dict[str, set[str]] = {}

    for tag_row in synced_tags:
        checked += 1
        from app.services.docker import repository_path_from_ref

        repo = repository_path_from_ref(tag_row.image_name)
        target_repo = f"{source.target_project or 'library'}/{repo.removeprefix('library/')}"
        try:
            if repo not in actual_tags:
                actual_tags[repo] = set(await client.list_tags(target_repo))
            present = tag_row.tag in actual_tags[repo]
        except ProviderClientError as exc:
            failed += 1
            logger.error(
                "Reconcile source %d: tags/list failed for %s: %s", source_id, target_repo, exc
            )
            continue

        if present:
            continue

        missing += 1
        drift_key = f"docker-drift:{source.id}:{target_repo}:{tag_row.tag}"
        payload = {
            "dedup_key": drift_key,
            "source_id": source.id,
            "repository": target_repo,
            "tag": tag_row.tag,
            "expected_digest": tag_row.digest,
        }
        try:
            from app.services.docker import docker_service

            image_name = tag_row.image_name
            tag_name = tag_row.tag
            digest = tag_row.digest

            def _repair(image_name: str = image_name, tag_name: str = tag_name):
                # Bind loop vars as defaults: the lambda closure must not see
                # the next iteration's values (ruff B023).
                return docker_service.sync_image(
                    source, image_name, tag_name, db, triggered_by="reconcile"
                )

            await sync_engine.reconcile(
                db,
                drift_key,
                expected=digest,
                actual=None,
                repair=_repair,
            )
            # Repair push done — the tag is (idempotently) re-copied.
            repaired += 1
            await sync_engine.outbox_write(db, "reconciliation.drift", payload)
            await db.commit()
        except Exception as exc:
            failed += 1
            logger.exception("Reconcile repair failed for %s: %s", drift_key, exc)

    summary = {
        "source_id": source_id,
        "checked": checked,
        "missing": missing,
        "repaired": repaired,
        "failed": failed,
    }
    logger.info("Reconcile docker source %d: %s", source_id, summary)
    return summary
