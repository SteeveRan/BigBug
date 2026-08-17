import asyncio
import base64
import json
import os
import re
import shutil
import tempfile
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ExternalServiceError, NotFoundError
from app.core.secrets import decrypt_secret
from app.models.credential import Credential
from app.models.docker_image_source import DockerImageSource
from app.models.docker_image_tag import DockerImageTag
from app.models.docker_sync_log import DockerSyncLog
from app.models.resource_provider import (
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.services.providers.clients.docker_auth import oci_request

# ──── Registry Parsing Utilities ────────────────────────────────────────────


# Map of known registry hostnames to providers
_REGISTRY_HOST_TO_PROVIDER: dict[str, str] = {
    "registry-1.docker.io": "docker_hub",
    "docker.io": "docker_hub",
    "index.docker.io": "docker_hub",
    "quay.io": "quay_io",
    "gcr.io": "gcr",
    "us.gcr.io": "gcr",
    "eu.gcr.io": "gcr",
    "asia.gcr.io": "gcr",
    "public.ecr.aws": "ecr",
    "mcr.microsoft.com": "acr",
    "ghcr.io": "ghcr",
}

_DOCKER_HUB_HOSTS = {"registry-1.docker.io", "docker.io", "index.docker.io"}

# Map legacy detection strings (RegistryProvider enum / _REGISTRY_HOST_TO_PROVIDER)
# to the unified ProviderSubtype used by ResourceProvider.
_PROVIDER_TO_SUBTYPE: dict[str, ProviderSubtype] = {
    "docker_hub": ProviderSubtype.docker_hub,
    "quay_io": ProviderSubtype.quay,
    "gcr": ProviderSubtype.gcr,
    "ecr": ProviderSubtype.ecr,
    "acr": ProviderSubtype.acr,
    "ghcr": ProviderSubtype.ghcr,
    "harbor": ProviderSubtype.harbor,
    "generic": ProviderSubtype.generic_registry,
}


def parse_registry_from_image(image_name: str) -> tuple[str, str]:
    """
    Parse registry host and provider from an image reference.

    Examples:
        nginx:latest             -> ('registry-1.docker.io', 'docker_hub')
        library/nginx:latest     -> ('registry-1.docker.io', 'docker_hub')
        quay.io/prom/node:latest -> ('quay.io', 'quay_io')
        myregistry.com/foo:tag   -> ('myregistry.com', 'generic')

    Returns (registry_host, provider) tuple.
    """
    image_name = image_name.strip()
    # Remove tag/digest for parsing
    if ":" in image_name:
        # Could be tag or port, careful
        image_name = image_name.split("@")[0]

    parts = image_name.split("/")

    # Single segment: library image on Docker Hub
    if len(parts) == 1:
        return ("registry-1.docker.io", "docker_hub")

    first = parts[0]

    # Check if first part looks like a registry hostname (contains a dot or colon-port)
    if "." in first or ":" in first:
        registry_host = first
        provider = _REGISTRY_HOST_TO_PROVIDER.get(registry_host, "generic")
        return (registry_host, provider)

    # First part is a Docker Hub username or "library"
    # e.g., library/nginx -> Docker Hub
    if first in ("library", "docker.io", "_"):
        return ("registry-1.docker.io", "docker_hub")

    # Two-part reference without dots: likely Docker Hub user/image
    # e.g., node:latest (single segment already handled), prom/node-exporter
    return ("registry-1.docker.io", "docker_hub")


def repository_path_from_ref(image_name: str) -> str:
    """Return the registry repository path (no host, no tag) for an image ref.

    Rules (deficit 2):
      1. ``strip()``; drop ``@digest``; drop ``:tag`` only from the last path
         segment (a ``host:port`` first segment is dropped together with the host).
      2. Drop a leading registry host (first segment containing ``.`` or ``:``,
         or ``localhost``).
      3. A single remaining segment on Docker Hub becomes ``library/<name>``.
      4. Return the remaining path.

    Examples:
        nginx                                 -> library/nginx
        library/nginx                         -> library/nginx
        nginx:1.25                            -> library/nginx
        docker.io/library/nginx:1.25          -> library/nginx
        registry-1.docker.io/library/nginx    -> library/nginx
        quay.io/prom/node-exporter:v1.0       -> prom/node-exporter
        harbor.local:443/bigbug/nginx         -> bigbug/nginx
        ghcr.io/org/img@sha256:abc            -> org/img
    """
    ref = image_name.strip()
    if not ref:
        return ""

    # Digest is not part of the repository path.
    ref = ref.split("@", 1)[0]

    # Strip the tag from the last path segment only.
    parts = ref.split("/")
    tail = parts[-1]
    if ":" in tail:
        parts[-1], _ = tail.rsplit(":", 1)
        ref = "/".join(parts)

    parts = ref.split("/")
    first = parts[0]
    # A registry host carries a dot, a port colon, or is literally localhost.
    if "." in first or ":" in first or first == "localhost":
        parts = parts[1:]

    is_docker_hub = parse_registry_from_image(image_name)[0] in _DOCKER_HUB_HOSTS

    if len(parts) == 1 and is_docker_hub:
        return f"library/{parts[0]}"
    return "/".join(parts)


def ref_tag(image_name: str) -> str:
    """Extract the tag from an image ref (default ``latest``).

    A digest ref (``@sha256:…``) has no meaningful tag for a tag-based mirror,
    so ``latest`` is returned. ponytail: mirror-by-digest is intentionally not
    supported — this is the documented fallback, not a full digest copy.
    """
    ref = image_name.strip()
    if "@" in ref:
        return "latest"
    tail = ref.split("/")[-1]
    if ":" in tail:
        _, tag = tail.rsplit(":", 1)
        return tag or "latest"
    return "latest"


def _registry_root(url: str) -> str:
    """Return a registry ``host[:port]`` without scheme or trailing ``/v2``.

    crane parses references with the OCI distribution spec, which does not
    accept an ``https://`` scheme prefix. The stored registry URLs carry a
    scheme (``https://harbor.local:443``), so we strip it before composing
    ``source_ref``/``target_ref`` for ``crane copy``.
    """
    url = url.strip().rstrip("/")
    url = re.sub(r"^https?://", "", url)
    if url.endswith("/v2"):
        url = url[:-3].rstrip("/")
    return url


def detect_provider_from_url(url: str) -> str:
    """Detect registry provider from a registry URL."""
    url_lower = url.lower()
    for host, provider in _REGISTRY_HOST_TO_PROVIDER.items():
        if host in url_lower:
            return provider
    return "generic"


def normalize_registry_image_ref(image_name: str) -> str:
    """
    Normalize an image reference to a full canonical form.

    nginx:latest -> registry-1.docker.io/library/nginx:latest
    quay.io/prom/node:latest -> quay.io/prometheus/node-exporter:latest
    """
    registry_host, _ = parse_registry_from_image(image_name)

    # Extract tag
    tag = "latest"
    name_part = image_name
    if ":" in image_name and "@" not in image_name:
        name_part, tag = image_name.rsplit(":", 1)

    # Build normalized path
    if registry_host == "registry-1.docker.io":
        parts = name_part.split("/")
        if len(parts) == 1:
            normalized = f"library/{parts[0]}"
        elif parts[0] in ("library", "docker.io", "_") or "." not in parts[0]:
            normalized = "/".join(parts)
        else:
            normalized = "/".join(parts[1:])
        return f"{registry_host}/{normalized}:{tag}"

    # Other registries: strip registry host from path
    parts = name_part.split("/")
    remaining = "/".join(parts[1:]) if parts[0] == registry_host else "/".join(parts)
    return f"{registry_host}/{remaining}:{tag}"


def _normalize_registry_url(url: str) -> str:
    """Ensure the URL ends with '/v2/' for a Docker Registry API v2 base."""
    url = url.rstrip("/")
    if not url.endswith("/v2"):
        url = f"{url}/v2"
    return url


def _validate_registry_url(url: str) -> None:
    """Raise BadRequestError if the URL is not a plausible Docker registry."""
    if not re.match(r"^https?://", url):
        raise BadRequestError(f"Docker registry URL must start with http:// or https://: {url}")


async def _get_docker_provider_or_404(
    db: AsyncSession,
    provider_id: int,
    *,
    internal_only: bool = False,
) -> ResourceProvider:
    """Fetch and validate a docker resource provider.

    Providers V3 rule (plans/features/providers-unified.md 11.3.4):
    ``docker_image_sources.target_provider_id`` must reference an internal
    provider with subtype harbor or generic_registry. Source providers
    (``provider_id``) must be docker-domain external rows.
    """
    result = await db.execute(
        select(ResourceProvider).where(
            ResourceProvider.id == provider_id,
            ~ResourceProvider.is_deleted,
        )
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise NotFoundError(f"Provider with id={provider_id} not found")
    if provider.domain != ProviderDomain.docker:
        raise BadRequestError(
            f"Provider {provider_id} is domain '{provider.domain}', expected 'docker'"
        )
    if internal_only:
        allowed = (ProviderSubtype.harbor, ProviderSubtype.generic_registry)
        if provider.subtype not in allowed or provider.direction != ProviderDirection.internal:
            raise BadRequestError(
                f"Provider {provider_id} ({provider.subtype}/{provider.direction}) cannot "
                "be a mirror target: target_provider_id requires an internal provider "
                "with subtype harbor or generic_registry"
            )
    return provider


def _provider_host(base_url: str | None) -> str:
    """Return the normalized host of a provider ``base_url`` (no scheme/path)."""
    if not base_url:
        return ""
    value = base_url.strip().lower()
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value.split("/", 1)[0].rstrip("/")


def _subtype_for_provider(provider: str | None) -> ProviderSubtype | None:
    """Map a legacy detection string to a unified ProviderSubtype, if known."""
    if not provider:
        return None
    return _PROVIDER_TO_SUBTYPE.get(provider)


async def find_matching_docker_provider(
    db: AsyncSession,
    registry_host: str,
    provider: str | None = None,
) -> ResourceProvider | None:
    """Find the best matching external docker ResourceProvider for a registry host.

    Replaces the legacy ``DockerRegistryInstanceService.find_matching_registry``
    (phase 7C). Match priority mirrors the old logic:
      1. exact ``base_url`` host match;
      2. subtype match (from the detected provider);
      3. the highest-priority active external docker provider.
    """
    result = await db.execute(
        select(ResourceProvider).where(
            ResourceProvider.domain == ProviderDomain.docker,
            ResourceProvider.is_active.is_(True),
            ResourceProvider.is_deleted.is_(False),
        )
    )
    active = list(result.scalars().all())
    if not active:
        return None

    # 1. Exact host match.
    for r in active:
        if _provider_host(r.base_url) == registry_host:
            return r

    # 2. Subtype match.
    subtype = _subtype_for_provider(provider)
    if subtype is not None:
        for r in active:
            if r.subtype == subtype:
                return r

    # 3. Default by priority (external first, highest priority wins).
    external = [r for r in active if r.direction == ProviderDirection.external]
    if external:
        return sorted(
            external,
            key=lambda r: (-r.priority, -int(r.is_default), r.name),
        )[0]

    return None


async def get_compatible_docker_providers(
    db: AsyncSession,
    registry_host: str,
    provider: str | None = None,
) -> list[ResourceProvider]:
    """Return active docker providers that can serve as the **source** for a host."""
    result = await db.execute(
        select(ResourceProvider).where(
            ResourceProvider.domain == ProviderDomain.docker,
            ResourceProvider.is_active.is_(True),
            ResourceProvider.is_deleted.is_(False),
        )
    )
    active = list(result.scalars().all())
    if not active:
        return []

    subtype = _subtype_for_provider(provider)
    compatible = [
        r
        for r in active
        if _provider_host(r.base_url) == registry_host
        or (subtype is not None and r.subtype == subtype)
    ]

    if not compatible:
        compatible = [r for r in active if r.direction == ProviderDirection.external]

    return sorted(compatible, key=lambda r: (-r.priority, r.name))


async def get_internal_docker_targets(db: AsyncSession) -> list[ResourceProvider]:
    """Return active internal docker providers usable as mirror targets.

    Filter: domain == docker, active, not deleted, direction == internal,
    subtype in (harbor, generic_registry). Sorted by ``(-priority, name)``.
    """
    result = await db.execute(
        select(ResourceProvider).where(
            ResourceProvider.domain == ProviderDomain.docker,
            ResourceProvider.is_active.is_(True),
            ResourceProvider.is_deleted.is_(False),
            ResourceProvider.direction == ProviderDirection.internal,
            ResourceProvider.subtype.in_(
                (ProviderSubtype.harbor, ProviderSubtype.generic_registry)
            ),
        )
    )
    providers = list(result.scalars().all())
    return sorted(providers, key=lambda r: (-r.priority, r.name))


class DockerRegistryService:
    """Service for indexing Docker image tags from a container registry.

    Queries the Docker Registry HTTP API v2 to list tags for a given
    image and creates/updates DockerImageTag entries in the database.
    """

    async def import_source_from_url(
        self,
        name: str,
        registry_url: str,
        image_name: str | None,
        db: AsyncSession,
        target_registry_url: str | None = None,
        target_project: str | None = None,
        provider_id: int | None = None,
        target_provider_id: int | None = None,
    ) -> DockerImageSource:
        """Create a new DockerImageSource from a registry URL and index it.

        Providers V3: ``provider_id`` links an external docker ResourceProvider;
        ``target_provider_id`` links the internal (harbor/generic_registry)
        target provider (11.3.4) and replaces the free-form
        ``target_registry_url`` string. Phase 7C drops the legacy
        ``registry_instance_id`` link and the DockerRegistryInstanceService
        auto-detection fallback.
        """
        _validate_registry_url(registry_url)
        normalized_url = _normalize_registry_url(registry_url)

        # Check for uniqueness
        existing_result = await db.execute(
            select(DockerImageSource).where(DockerImageSource.name == name)
        )
        if existing_result.scalar_one_or_none() is not None:
            raise BadRequestError(f"Docker image source with name '{name}' already exists")

        # Providers V3: validate both links up-front (11.3.4).
        if provider_id is not None:
            await _get_docker_provider_or_404(db, provider_id)
        if target_provider_id is not None:
            await _get_docker_provider_or_404(db, target_provider_id, internal_only=True)
            # Keep the legacy URL column in sync so the crane mirror path
            # keeps working until it is switched to the provider (phase 6/7).
            if not target_registry_url:
                tp = await db.get(ResourceProvider, target_provider_id)
                target_registry_url = tp.base_url

        # Providers V3 (phase 7C): auto-resolve an external docker provider when
        # no explicit provider_id is supplied.
        if provider_id is None:
            provider = detect_provider_from_url(registry_url)
            registry_host, _ = parse_registry_from_image(image_name or name)
            matched = await find_matching_docker_provider(db, registry_host, provider)
            if matched is not None:
                provider_id = matched.id

        source = DockerImageSource(
            name=name,
            registry_url=normalized_url,
            status_flag=4,
            target_registry_url=target_registry_url,
            target_project=target_project,
            provider_id=provider_id,
            target_provider_id=target_provider_id,
        )
        db.add(source)
        await db.flush()

        # Index the registry if an image name was provided. Normalize to the pure
        # repository path so old clients sending a canonical ref stay supported.
        if image_name:
            await self.index_source(source, repository_path_from_ref(image_name), db)

        await db.commit()
        await db.refresh(source)
        return source

    async def index_source(
        self,
        source: DockerImageSource,
        image_name: str,
        db: AsyncSession,
    ) -> DockerSyncLog:
        """Fetch tags for an image from the registry and sync them."""
        now = datetime.now(UTC)
        sync_log = DockerSyncLog(
            source_id=source.id,
            status_flag=3,  # in_progress
            status_text="indexing",
            triggered_by="manual",
            started_at=now,
        )
        db.add(sync_log)
        await db.flush()

        source.status_flag = 3  # type: ignore[assignment]
        source.status_text = "indexing"  # type: ignore[assignment]

        try:
            basic, verify_ssl = await self._resolve_auth(db, source.provider_id)
            tags_data = await self._fetch_tags(
                source.registry_url, image_name, basic=basic, verify_ssl=verify_ssl
            )
        except Exception as e:
            sync_log.status_flag = 1  # type: ignore[assignment]
            sync_log.status_text = "failed"  # type: ignore[assignment]
            sync_log.log_output = str(e)  # type: ignore[assignment]
            sync_log.finished_at = datetime.now(UTC)  # type: ignore[assignment]
            source.status_flag = 1  # type: ignore[assignment]
            source.status_text = f"Failed to fetch tags: {e}"  # type: ignore[assignment]
            await db.flush()
            return sync_log

        try:
            tag_count = await self._sync_tags(source, image_name, tags_data, db)
        except Exception as e:
            sync_log.status_flag = 1  # type: ignore[assignment]
            sync_log.status_text = "failed"  # type: ignore[assignment]
            sync_log.log_output = f"Failed to sync tags: {e}"  # type: ignore[assignment]
            sync_log.finished_at = datetime.now(UTC)  # type: ignore[assignment]
            source.status_flag = 1  # type: ignore[assignment]
            source.status_text = f"Tag sync error: {e}"  # type: ignore[assignment]
            await db.flush()
            return sync_log

        sync_log.status_flag = 0  # type: ignore[assignment]
        sync_log.status_text = "success"  # type: ignore[assignment]
        sync_log.log_output = (  # type: ignore[assignment]
            f"Indexed {tag_count} tag(s) for {image_name} from {source.registry_url}"
        )
        sync_log.finished_at = datetime.now(UTC)  # type: ignore[assignment]

        source.status_flag = 0  # type: ignore[assignment]
        source.status_text = "ok"  # type: ignore[assignment]
        source.last_synced_at = datetime.now(UTC)  # type: ignore[assignment]

        await db.flush()
        return sync_log

    async def _fetch_tags(
        self,
        registry_url: str,
        image_name: str,
        *,
        basic: tuple[str, str] | None = None,
        verify_ssl: bool = True,
    ) -> dict[str, Any]:
        """Fetch tags list and metadata from Docker Registry API v2.

        The repository path is normalized via :func:`repository_path_from_ref`
        so a canonical ref (host + tag) still hits ``/v2/<repo>/tags/list``.
        """
        base_url = registry_url.rstrip("/")
        repo = repository_path_from_ref(image_name)
        if not repo:
            raise BadRequestError("Image reference does not contain a repository path")
        tags_url = f"{base_url}/{repo}/tags/list"

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, verify=verify_ssl
        ) as client:
            try:
                response = await oci_request(client, "GET", tags_url, basic=basic)
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise ExternalServiceError("Docker registry", f"HTTP error: {e}") from e

        try:
            data: dict[str, Any] = response.json()
        except Exception as e:
            raise ExternalServiceError("Docker registry", f"JSON parse error: {e}") from e

        if "tags" not in data:
            raise ExternalServiceError(
                "Docker registry",
                "Response does not contain 'tags' key — image may not exist",
            )

        return data

    async def _resolve_manifest_digest(
        self,
        client: httpx.AsyncClient,
        registry_url: str,
        image_name: str,
        tag: str,
        *,
        basic: tuple[str, str] | None = None,
    ) -> str | None:
        """Fetch the manifest digest for a specific image:tag (HEAD request)."""
        base_url = registry_url.rstrip("/")
        repo = repository_path_from_ref(image_name)
        manifest_url = f"{base_url}/{repo}/manifests/{tag}"
        headers = {
            "Accept": (
                "application/vnd.docker.distribution.manifest.v2+json, "
                "application/vnd.oci.image.manifest.v1+json, "
                "application/vnd.docker.distribution.manifest.list.v2+json"
            ),
        }

        try:
            response = await oci_request(
                client, "HEAD", manifest_url, basic=basic, headers=headers
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        return response.headers.get("docker-content-digest")

    async def _sync_tags(
        self,
        source: DockerImageSource,
        image_name: str,
        tags_data: dict[str, Any],
        db: AsyncSession,
    ) -> int:
        """Create or update DockerImageTag records from registry response."""
        tags: list[str] = tags_data.get("tags", [])
        if not tags:
            return 0

        # For each tag, resolve the manifest digest
        base_url = source.registry_url  # type: ignore[assignment]
        basic, verify_ssl = await self._resolve_auth(db, source.provider_id)
        tag_count = 0

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, verify=verify_ssl
        ) as client:
            for tag in tags:
                digest = await self._resolve_manifest_digest(
                    client, str(base_url), image_name, tag, basic=basic
                )

                # Check if this exact tag already exists
                existing_result = await db.execute(
                    select(DockerImageTag).where(
                        DockerImageTag.source_id == source.id,
                        DockerImageTag.image_name == image_name,
                        DockerImageTag.tag == tag,
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if existing:
                    existing.digest = digest  # type: ignore[assignment]
                    existing.last_synced_at = datetime.now(UTC)  # type: ignore[assignment]
                    if not existing.is_synced:  # type: ignore[comparison-overlap]
                        existing.is_synced = True  # type: ignore[assignment]
                else:
                    image_tag = DockerImageTag(
                        source_id=source.id,
                        image_name=image_name,
                        tag=tag,
                        digest=digest,
                        status_flag=0,  # ok — newly indexed
                        status_text="ok",
                        is_synced=True,
                        last_synced_at=datetime.now(UTC),
                    )
                    db.add(image_tag)

                tag_count += 1

        await db.flush()
        return tag_count

    async def refresh_source(
        self,
        source: DockerImageSource,
        image_name: str,
        db: AsyncSession,
    ) -> DockerSyncLog:
        """Re-index tags for an existing Docker image source."""
        return await self.index_source(source, image_name, db)

    async def _resolve_auth(
        self,
        db: AsyncSession,
        provider_id: int | None,
    ) -> tuple[tuple[str, str] | None, bool]:
        """Resolve ``(basic, verify_ssl)`` for a docker provider id.

        Returns ``(None, True)`` when there is no provider or credential so the
        registry is queried anonymously with TLS verification enabled.
        """
        verify_ssl = True
        if provider_id is None:
            return None, True
        provider = await db.get(ResourceProvider, provider_id)
        if provider is None:
            return None, True
        verify_ssl = provider.verify_ssl
        if provider.credential_id is None:
            return None, verify_ssl
        credential = await db.get(Credential, provider.credential_id)
        if credential is None:
            return None, verify_ssl
        secret = decrypt_secret(credential.encrypted_secret)
        if secret and credential.username:
            return (credential.username, secret), verify_ssl
        return None, verify_ssl

    async def _build_docker_auths(
        self,
        db: AsyncSession,
        source: DockerImageSource,
        target_provider: ResourceProvider | None,
        target_registry_url: str,
    ) -> dict[str, dict[str, str]]:
        """Build ``{"auths": {host: {"auth": base64(user:pass)}}}`` for crane.

        Source (Docker Hub) is anonymous by default; if a source credential exists
        it is added under the source host so crane picks it up. The target
        credential lives under the target host. Secrets are never passed via argv.
        """
        auths: dict[str, dict[str, str]] = {}

        async def _add(provider_id: int | None, host: str) -> None:
            if provider_id is None:
                return
            provider = await db.get(ResourceProvider, provider_id)
            if provider is None or provider.credential_id is None:
                return
            credential = await db.get(Credential, provider.credential_id)
            if credential is None:
                return
            secret = decrypt_secret(credential.encrypted_secret)
            if not secret or not credential.username:
                return
            raw = f"{credential.username}:{secret}".encode()
            auths[host] = {"auth": base64.b64encode(raw).decode("ascii")}

        if target_provider is not None:
            await _add(target_provider.id, _provider_host(target_registry_url))
        await _add(source.provider_id, _provider_host(source.registry_url))
        return auths

    async def mirror_image(
        self,
        source: DockerImageSource,
        image_name: str,
        tag: str,
        db: AsyncSession,
        triggered_by: str = "manual",
    ) -> DockerSyncLog:
        """Mirror a Docker image from the external source registry to the target registry.

        Uses crane CLI tool for copying images between registries.

        Providers V3 (phase 4): the target registry is resolved from
        ``target_provider_id`` (internal harbor/generic_registry provider,
        11.3.4); the legacy ``target_registry_url`` string is the fallback.
        """
        target_registry_url = source.target_registry_url
        target_provider: ResourceProvider | None = None
        if source.target_provider_id is not None:
            tp = await db.get(ResourceProvider, source.target_provider_id)
            if tp is not None and tp.base_url:
                target_provider = tp
                target_registry_url = tp.base_url
        if not target_registry_url:
            raise ValueError("Source has no target registry configured")

        repo = repository_path_from_ref(image_name)
        tag = tag or ref_tag(image_name)
        target_repo = repo.removeprefix("library/")

        # Create log entry
        log = DockerSyncLog(
            source_id=source.id,  # type: ignore[arg-type]
            status_flag=4,  # Pending
            status_text="Pending",
            triggered_by=triggered_by,
            started_at=datetime.now(UTC),
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)

        docker_config_dir: str | None = None

        try:
            # Update status to In Progress
            log.status_flag = 3  # type: ignore[assignment]
            log.status_text = "In Progress"  # type: ignore[assignment]
            await db.commit()

            # Build source and target references (no /v2 suffix for crane).
            source_ref = f"{_registry_root(source.registry_url)}/{repo}:{tag}"
            target_ref = (
                f"{_registry_root(target_registry_url)}/"
                f"{source.target_project or 'library'}/{target_repo}:{tag}"
            )

            # Build the temporary docker config.json (0600) so secrets never land
            # in argv. crane selects the right entry by registry host.
            auths = await self._build_docker_auths(
                db, source, target_provider, target_registry_url
            )
            env = os.environ.copy()
            if auths:
                docker_config_dir = tempfile.mkdtemp(prefix="bigbug-docker-config-")
                config_path = os.path.join(docker_config_dir, "config.json")
                with open(config_path, "w", encoding="utf-8") as handle:
                    json.dump({"auths": auths}, handle)
                os.chmod(config_path, 0o600)
                env["DOCKER_CONFIG"] = docker_config_dir

            cmd = ["crane", "copy"]
            if target_provider is not None and target_provider.verify_ssl is False:
                cmd.append("--insecure")
            cmd += [source_ref, target_ref]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
                # ponytail: single-image mirror is awaited inline; upgrade to a
                # task queue when mirroring becomes bulk/parallel.
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=1800
                )
            except FileNotFoundError as exc:
                raise ExternalServiceError(
                    "crane",
                    "crane binary is not installed in the backend image; "
                    "rebuild backend/docker/Dockerfile",
                ) from exc
            finally:
                if docker_config_dir:
                    shutil.rmtree(docker_config_dir, ignore_errors=True)

            if process.returncode == 0:
                log.status_flag = 0  # type: ignore[assignment]
                log.status_text = "Success"  # type: ignore[assignment]
                log.log_output = (  # type: ignore[assignment]
                    f"Successfully mirrored {source_ref} -> {target_ref}"
                )

                # Update or create the tag entry with sync status
                await self._mark_tag_synced(db, source.id, repo, tag)
                await db.commit()
            else:
                log.status_flag = 1  # type: ignore[assignment]
                log.status_text = "Failed"  # type: ignore[assignment]
                log.log_output = (  # type: ignore[assignment]
                    stderr.decode() if stderr else f"Exit code: {process.returncode}"
                )
                await db.commit()

        except ExternalServiceError:
            raise
        except Exception as e:
            log.status_flag = 1  # type: ignore[assignment]
            log.status_text = "Failed"  # type: ignore[assignment]
            log.log_output = str(e)  # type: ignore[assignment]
            await db.commit()

        finally:
            log.finished_at = datetime.now(UTC)  # type: ignore[assignment]
            await db.commit()

        return log

    async def _mark_tag_synced(
        self,
        db: AsyncSession,
        source_id: int,
        image_name: str,
        tag: str,
    ) -> None:
        """Mark a specific DockerImageTag as synced."""
        result = await db.execute(
            select(DockerImageTag).where(
                DockerImageTag.source_id == source_id,
                DockerImageTag.image_name == image_name,
                DockerImageTag.tag == tag,
            )
        )
        tag_record = result.scalar_one_or_none()
        if tag_record:
            tag_record.is_synced = True  # type: ignore[assignment]
            tag_record.status_flag = 0  # type: ignore[assignment]
            tag_record.status_text = "Synced"  # type: ignore[assignment]
            tag_record.last_synced_at = datetime.now(UTC)  # type: ignore[assignment]


docker_service = DockerRegistryService()
