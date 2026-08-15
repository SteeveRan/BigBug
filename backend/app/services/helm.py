import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ExternalServiceError, NotFoundError
from app.models.helm_chart_source import HelmChartSource
from app.models.helm_chart_version import HelmChartVersion
from app.models.helm_sync_log import HelmSyncLog
from app.models.resource_provider import (
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)


def _normalize_repo_url(url: str) -> str:
    """Ensure the URL ends with '/index.yaml' for a Helm repo."""
    url = url.rstrip("/")
    if not url.endswith("/index.yaml"):
        url = f"{url}/index.yaml"
    return url


def _validate_repo_url(url: str) -> None:
    """Raise BadRequestError if the URL is not a plausible Helm repo."""
    if not re.match(r"^https?://", url):
        raise BadRequestError(f"Helm repo URL must start with http:// or https://: {url}")


class HelmService:
    """Service for indexing Helm chart repositories.

    Fetches the index.yaml from a chart repository and creates/updates
    HelmChartVersion entries in the database.
    """

    async def import_source_from_url(
        self,
        name: str,
        repo_url: str,
        db: AsyncSession,
        provider_id: int | None = None,
    ) -> HelmChartSource:
        """Create a new HelmChartSource from a URL and index it.

        Providers V3 (phase 4): ``provider_id`` optionally links a helm
        ResourceProvider (domain=helm, subtype=helm_repo, direction=external).
        """
        _validate_repo_url(repo_url)
        normalized_url = _normalize_repo_url(repo_url)

        # Check for uniqueness
        existing_result = await db.execute(
            select(HelmChartSource).where(HelmChartSource.name == name)
        )
        if existing_result.scalar_one_or_none() is not None:
            raise BadRequestError(f"Helm chart source with name '{name}' already exists")

        if provider_id is not None:
            result = await db.execute(
                select(ResourceProvider).where(
                    ResourceProvider.id == provider_id,
                    ~ResourceProvider.is_deleted,
                )
            )
            provider = result.scalar_one_or_none()
            if provider is None:
                raise NotFoundError(f"Provider with id={provider_id} not found")
            if (
                provider.domain != ProviderDomain.helm
                or provider.subtype != ProviderSubtype.helm_repo
                or provider.direction != ProviderDirection.external
            ):
                raise BadRequestError(
                    f"Provider {provider_id} ({provider.domain}/{provider.subtype}/"
                    f"{provider.direction}) cannot be a helm source: expected "
                    "helm/helm_repo/external"
                )

        source = HelmChartSource(
            name=name,
            repo_url=normalized_url,
            status_flag=4,
            provider_id=provider_id,
        )
        db.add(source)
        await db.flush()

        # Index the repository
        await self.index_source(source, db)

        await db.commit()
        await db.refresh(source)
        return source

    async def index_source(self, source: HelmChartSource, db: AsyncSession) -> HelmSyncLog:
        """Fetch index.yaml and sync chart versions for a source."""
        now = datetime.now(UTC)
        sync_log = HelmSyncLog(
            source_id=source.id,
            status_flag=3,  # in_progress
            status_text="indexing",
            triggered_by="manual",
            started_at=now,
        )
        db.add(sync_log)
        await db.flush()

        source.status_flag = 3
        source.status_text = "indexing"

        try:
            index = await self._fetch_index(source.repo_url)
        except Exception as e:
            sync_log.status_flag = 1
            sync_log.status_text = "failed"
            sync_log.log_output = str(e)
            sync_log.finished_at = datetime.now(UTC)
            source.status_flag = 1
            source.status_text = f"Failed to fetch index: {e}"
            await db.flush()
            return sync_log

        entries: dict[str, list[dict[str, Any]]] = index.get("entries", {})

        try:
            await self._sync_chart_entries(source, entries, db)
        except Exception as e:
            sync_log.status_flag = 1
            sync_log.status_text = "failed"
            sync_log.log_output = f"Failed to sync entries: {e}"
            sync_log.finished_at = datetime.now(UTC)
            source.status_flag = 1
            source.status_text = f"Entry sync error: {e}"
            await db.flush()
            return sync_log

        sync_log.status_flag = 0
        sync_log.status_text = "success"
        sync_log.log_output = f"Indexed {len(entries)} chart(s) from {source.repo_url}"
        sync_log.finished_at = datetime.now(UTC)

        source.status_flag = 0
        source.status_text = "ok"
        source.last_synced_at = datetime.now(UTC)

        await db.flush()
        return sync_log

    async def _fetch_index(self, repo_url: str) -> dict[str, Any]:
        """Download and parse index.yaml."""
        headers: dict[str, str] = {"Accept": "application/x-yaml, application/yaml, text/yaml"}

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(repo_url, headers=headers)
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise ExternalServiceError("Helm repo", f"HTTP error: {e}") from e

        try:
            data = yaml.safe_load(response.text)
        except yaml.YAMLError as e:
            raise ExternalServiceError("Helm repo", f"YAML parse error: {e}") from e

        if not isinstance(data, dict) or "entries" not in data:
            raise ExternalServiceError("Helm repo", "index.yaml does not contain 'entries' key")

        return data

    async def _sync_chart_entries(
        self,
        source: HelmChartSource,
        entries: dict[str, list[dict[str, Any]]],
        db: AsyncSession,
    ) -> None:
        """Create or update chart version records from index.yaml entries."""
        for chart_name, versions in entries.items():
            for entry in versions:
                version_str = entry.get("version", "0.0.0")
                digest = entry.get("digest")

                # Check if this exact version already exists
                existing_result = await db.execute(
                    select(HelmChartVersion).where(
                        HelmChartVersion.source_id == source.id,
                        HelmChartVersion.chart_name == chart_name,
                        HelmChartVersion.version == version_str,
                    )
                )
                existing = existing_result.scalar_one_or_none()

                if existing:
                    # Update metadata (digest may have changed)
                    existing.digest = digest
                    existing.app_version = entry.get("appVersion")
                    existing.description = entry.get("description")
                    existing.urls = json.dumps(entry.get("urls", []))
                    existing.chart_url = entry.get("urls", [None])[0] if entry.get("urls") else None
                else:
                    chart_version = HelmChartVersion(
                        source_id=source.id,
                        chart_name=chart_name,
                        version=version_str,
                        app_version=entry.get("appVersion"),
                        description=entry.get("description"),
                        digest=digest,
                        urls=json.dumps(entry.get("urls", [])),
                        chart_url=(entry.get("urls", [None])[0] if entry.get("urls") else None),
                        status_flag=0,  # ok — newly indexed
                        status_text="ok",
                        is_synced=True,
                        last_synced_at=datetime.now(UTC),
                    )
                    db.add(chart_version)

        await db.flush()

    async def refresh_source(self, source: HelmChartSource, db: AsyncSession) -> HelmSyncLog:
        """Re-index an existing Helm chart source."""
        return await self.index_source(source, db)

    def trigger_index_pipeline(
        self, source: HelmChartSource, db: AsyncSession, triggered_by: str = "manual"
    ) -> HelmSyncLog:
        """Trigger a GitLab pipeline for Helm chart indexing. (Sync wrapper.)

        Creates a HelmSyncLog entry with status pending. The actual pipeline
        execution happens in GitLab CI via the helm-sync-template.
        """
        now = datetime.now(UTC)
        sync_log = HelmSyncLog(
            source_id=source.id,
            status_flag=4,  # pending
            status_text="pipeline triggered",
            triggered_by=triggered_by,
            started_at=now,
        )
        db.add(sync_log)
        source.status_flag = 3
        source.status_text = "sync in progress"
        return sync_log


helm_service = HelmService()
