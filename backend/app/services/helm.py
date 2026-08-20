import json
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import gitlab
import httpx
import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ExternalServiceError, NotFoundError
from app.core.secrets import decrypt_secret
from app.models.helm_chart_source import HelmChartSource
from app.models.helm_chart_version import HelmChartVersion
from app.models.helm_sync_log import HelmSyncLog
from app.models.resource_provider import (
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.services.gitlab import get_default_gitlab_provider

if TYPE_CHECKING:
    pass


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


async def mark_helm_version_synced(
    db: AsyncSession,
    source_id: int,
    chart_name: str,
    version: str,
) -> None:
    """Mark a specific HelmChartVersion as synced after a successful mirror.

    Called by the GitLab webhook once the mirror pipeline reports success, so
    ``is_synced`` reflects a real copy into the target repo — never a mere
    index run.
    """
    result = await db.execute(
        select(HelmChartVersion).where(
            HelmChartVersion.source_id == source_id,
            HelmChartVersion.chart_name == chart_name,
            HelmChartVersion.version == version,
        )
    )
    version_row = result.scalar_one_or_none()
    if version_row is None:
        return
    version_row.is_synced = True
    version_row.status_flag = 0
    version_row.status_text = "Synced"
    version_row.last_synced_at = datetime.now(UTC)


class HelmService:
    """Service for indexing Helm chart repositories and mirroring chart versions.

    Fetches the index.yaml from a chart repository and creates/updates
    HelmChartVersion entries in the database. Mirroring a single version
    triggers a GitLab CI pipeline (helm-sync-template) that actually copies the
    chart into the target repository; the webhook then marks it as synced.
    """

    async def import_source_from_url(
        self,
        name: str,
        repo_url: str,
        db: AsyncSession,
        provider_id: int | None = None,
        target_repo_url: str | None = None,
    ) -> HelmChartSource:
        """Create a new HelmChartSource from a URL and index it.

        Providers V3 (phase 4): ``provider_id`` optionally links a helm
        ResourceProvider (domain=helm, subtype=helm_repo, direction=external).
        ``target_repo_url`` is the repository charts are mirrored into.
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
            target_repo_url=target_repo_url,
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
        """Create or update chart version records from index.yaml entries.

        Indexing only records available versions; it never marks a version as
        synced (``is_synced`` stays False / status stays pending). Only a
        successful mirror via :meth:`mirror_chart` (confirmed by the webhook)
        flips ``is_synced``.
        """
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
                    # Update metadata (digest may have changed). Sync state is
                    # intentionally left untouched here.
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
                        status_flag=4,  # pending — indexed but not mirrored yet
                        status_text="pending",
                        is_synced=False,
                    )
                    db.add(chart_version)

        await db.flush()

    async def refresh_source(self, source: HelmChartSource, db: AsyncSession) -> HelmSyncLog:
        """Re-index an existing Helm chart source."""
        return await self.index_source(source, db)

    def _get_client(self, provider: ResourceProvider | None = None) -> gitlab.Gitlab:
        """Build a python-gitlab client (provider-first, settings fallback)."""
        if provider is not None:
            token: str | None = None
            if provider.credential is not None and provider.credential.encrypted_secret:
                token = decrypt_secret(provider.credential.encrypted_secret)
            return gitlab.Gitlab(
                provider.base_url,
                private_token=token or None,
                ssl_verify=provider.verify_ssl,
            )
        if settings.gitlab_url:
            return gitlab.Gitlab(
                settings.gitlab_url,
                private_token=settings.gitlab_token or None,
            )
        return gitlab.Gitlab()

    async def _get_version(
        self,
        source_id: int,
        chart_name: str,
        version: str,
        db: AsyncSession,
    ) -> HelmChartVersion | None:
        result = await db.execute(
            select(HelmChartVersion).where(
                HelmChartVersion.source_id == source_id,
                HelmChartVersion.chart_name == chart_name,
                HelmChartVersion.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def mirror_chart(
        self,
        source: HelmChartSource,
        chart_name: str,
        version: str,
        db: AsyncSession,
        triggered_by: str = "manual",
    ) -> HelmSyncLog:
        """Mirror one chart version into the target Helm repository.

        Triggers a GitLab CI pipeline (helm-sync-template) which performs the
        actual ``helm pull`` / ``helm push``. The log stores ``chart_name`` /
        ``chart_version`` so the webhook can mark the exact version as synced
        on success. ``is_synced`` is only ever set after that success.
        """
        version_row = await self._get_version(source.id, chart_name, version, db)
        if version_row is None:
            raise NotFoundError(
                f"Chart version '{chart_name}:{version}' not found; index the source first"
            )

        if not source.gitlab_project_id:
            raise BadRequestError(
                "Helm chart source has no GitLab project configured for mirroring"
            )

        now = datetime.now(UTC)
        log = HelmSyncLog(
            source_id=source.id,
            chart_name=chart_name,
            chart_version=version,
            status_flag=4,  # pending
            status_text="pending",
            triggered_by=triggered_by,
            started_at=now,
        )
        db.add(log)
        await db.flush()

        provider = await get_default_gitlab_provider(db)
        try:
            gl = self._get_client(provider)
            gl_project = gl.projects.get(source.gitlab_project_id)
            pipeline = gl_project.pipelines.create(
                {
                    "ref": "main",
                    "variables": [
                        {"key": "HELM_REPO_URL", "value": source.repo_url},
                        {"key": "HELM_REPO_NAME", "value": source.name},
                        {"key": "CHART_NAME", "value": chart_name},
                        {"key": "CHART_VERSION", "value": version},
                        {"key": "TARGET_REPO_URL", "value": source.target_repo_url or ""},
                    ],
                }
            )
        except gitlab.exceptions.GitlabError as e:
            log.status_flag = 1
            log.status_text = f"Failed to trigger pipeline: {e}"
            log.finished_at = datetime.now(UTC)
            await db.flush()
            raise ExternalServiceError("GitLab", str(e)) from e

        base_url = provider.base_url if provider is not None else settings.gitlab_url
        log.pipeline_id = str(pipeline.id)
        log.pipeline_url = f"{base_url}/{source.gitlab_project_id}/-/pipelines/{pipeline.id}"
        log.status_flag = 3  # in_progress
        log.status_text = "running"

        source.status_flag = 3
        source.status_text = "sync in progress"

        await db.flush()
        return log


helm_service = HelmService()
