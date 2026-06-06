import re
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ExternalServiceError
from app.models.docker_image_source import DockerImageSource
from app.models.docker_image_tag import DockerImageTag
from app.models.docker_sync_log import DockerSyncLog


def _normalize_registry_url(url: str) -> str:
    """Ensure the URL ends with '/v2/' for a Docker Registry API v2 base."""
    url = url.rstrip("/")
    if not url.endswith("/v2"):
        url = f"{url}/v2"
    return url


def _validate_registry_url(url: str) -> None:
    """Raise BadRequestError if the URL is not a plausible Docker registry."""
    if not re.match(r"^https?://", url):
        raise BadRequestError(
            f"Docker registry URL must start with http:// or https://: {url}"
        )


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
    ) -> DockerImageSource:
        """Create a new DockerImageSource from a registry URL and index it."""
        _validate_registry_url(registry_url)
        normalized_url = _normalize_registry_url(registry_url)

        # Check for uniqueness
        existing_result = await db.execute(
            select(DockerImageSource).where(DockerImageSource.name == name)
        )
        if existing_result.scalar_one_or_none() is not None:
            raise BadRequestError(
                f"Docker image source with name '{name}' already exists"
            )

        source = DockerImageSource(
            name=name,
            registry_url=normalized_url,
            status_flag=4,
        )
        db.add(source)
        await db.flush()

        # Index the registry if an image name was provided
        if image_name:
            await self.index_source(source, image_name, db)

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
            tags_data = await self._fetch_tags(source.registry_url, image_name)
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

    async def _fetch_tags(self, registry_url: str, image_name: str) -> dict[str, Any]:
        """Fetch tags list and metadata from Docker Registry API v2.

        Uses two endpoints:
        1. GET /v2/<image>/tags/list — list of tags
        2. GET /v2/<image>/manifests/<tag> — per-tag digest + metadata (HEAD)
        """
        base_url = registry_url.rstrip("/")
        tags_url = f"{base_url}/{image_name}/tags/list"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(tags_url)
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise ExternalServiceError("Docker registry", f"HTTP error: {e}")

        try:
            data: dict[str, Any] = response.json()
        except Exception as e:
            raise ExternalServiceError("Docker registry", f"JSON parse error: {e}")

        if "tags" not in data:
            raise ExternalServiceError(
                "Docker registry",
                "Response does not contain 'tags' key — image may not exist",
            )

        return data

    async def _resolve_manifest_digest(
        self, client: httpx.AsyncClient, registry_url: str, image_name: str, tag: str
    ) -> str | None:
        """Fetch the manifest digest for a specific image:tag (HEAD request)."""
        base_url = registry_url.rstrip("/")
        manifest_url = f"{base_url}/{image_name}/manifests/{tag}"
        headers = {
            "Accept": (
                "application/vnd.docker.distribution.manifest.v2+json, "
                "application/vnd.oci.image.manifest.v1+json, "
                "application/vnd.docker.distribution.manifest.list.v2+json"
            ),
        }

        try:
            response = await client.head(manifest_url, headers=headers)
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
        tag_count = 0

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for tag in tags:
                digest = await self._resolve_manifest_digest(
                    client, str(base_url), image_name, tag
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


docker_service = DockerRegistryService()
