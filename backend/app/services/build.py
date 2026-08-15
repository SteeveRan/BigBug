"""
@file build.py
@description Build service — trigger GitLab pipelines for gold and app image
             builds. Resolves the active platform GitLab from
             ``resource_providers`` (subtype=gitlab, category=system,
             direction=internal); falls back to settings.GITLAB_URL /
             settings.GITLAB_TOKEN for backward compatibility.
@dependencies python-gitlab, app.config.settings, app.core.secrets
@relatedFiles ../models/resource_provider.py, ../models/gold_image.py,
               ../models/app_image.py, ./gitlab.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import gitlab
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ExternalServiceError
from app.core.secrets import decrypt_secret
from app.models.app_image import AppImage
from app.models.build_log import BuildLog
from app.models.gold_image import GoldImage
from app.models.image_version import ImageVersion
from app.services.gitlab import get_default_gitlab_provider

if TYPE_CHECKING:
    from app.models.resource_provider import ResourceProvider


class BuildService:
    # ------------------------------------------------------------------
    # Provider resolution
    # ------------------------------------------------------------------

    @staticmethod
    async def get_default_instance(db: AsyncSession) -> ResourceProvider | None:
        """Return the default platform GitLab provider from resource_providers."""
        return await get_default_gitlab_provider(db)

    # ------------------------------------------------------------------
    # Client factory
    # ------------------------------------------------------------------

    def _get_client(self, provider: ResourceProvider | None = None) -> gitlab.Gitlab:
        """
        Build a python-gitlab client.

        Priority:
        1. ``provider`` — use its base_url and *decrypted* credential secret.
        2. ``settings.gitlab_url`` and ``settings.gitlab_token`` (fallback).
        3. ``settings.gitlab_url`` without auth.
        """
        if provider is not None:
            token: str | None = None
            if provider.credential is not None and provider.credential.encrypted_secret:
                token = decrypt_secret(provider.credential.encrypted_secret)
            return gitlab.Gitlab(
                provider.base_url,
                private_token=token or None,
                ssl_verify=provider.verify_ssl,
            )

        # Backward-compatible fallback
        if settings.gitlab_url:
            return gitlab.Gitlab(
                settings.gitlab_url,
                private_token=settings.gitlab_token or None,
            )
        return gitlab.Gitlab()

    def _pipeline_base_url(self, provider: ResourceProvider | None) -> str:
        """Return the base URL for constructing pipeline links."""
        if provider is not None:
            return provider.base_url or settings.gitlab_url
        return settings.gitlab_url

    # ------------------------------------------------------------------
    # Build triggers
    # ------------------------------------------------------------------

    async def trigger_gold_build(
        self,
        image: GoldImage,
        version_tag: str,
        arch: str,
        db: AsyncSession,
        triggered_by: str = "manual",
        *,
        provider: ResourceProvider | None = None,
    ) -> ImageVersion:
        """Trigger a GitLab pipeline to build a gold image version."""
        if not image.gitlab_project_id:
            raise BadRequestError("Gold image has no GitLab project configured")

        if provider is None:
            provider = await self.get_default_instance(db)

        version = ImageVersion(
            image_type="gold",
            gold_image_id=image.id,
            version_tag=version_tag,
            arch=arch,
            status_flag=4,  # pending
            status_text="pending",
        )
        db.add(version)
        await db.flush()

        try:
            gl = self._get_client(provider)
            gl_project = gl.projects.get(image.gitlab_project_id)
            pipeline = gl_project.pipelines.create(
                {
                    "ref": "main",
                    "variables": [
                        {"key": "VERSION_TAG", "value": version_tag},
                        {"key": "TARGET_ARCH", "value": arch},
                        {"key": "IMAGE_VERSION_ID", "value": str(version.id)},
                    ],
                }
            )
        except gitlab.exceptions.GitlabError as e:
            version.status_flag = 1
            version.status_text = f"Failed to trigger pipeline: {e}"
            await db.commit()
            raise ExternalServiceError("GitLab", str(e)) from e

        base_url = self._pipeline_base_url(provider)
        now = datetime.now(UTC)
        build_log = BuildLog(
            image_version_id=version.id,
            pipeline_id=str(pipeline.id),
            pipeline_url=f"{base_url}/{image.gitlab_project_id}/-/pipelines/{pipeline.id}",
            status_flag=3,  # in_progress
            status_text="running",
            triggered_by=triggered_by,
            started_at=now,
        )
        db.add(build_log)

        version.status_flag = 3
        version.status_text = "running"

        await db.commit()
        await db.refresh(version)
        return version

    async def trigger_app_build(
        self,
        image: AppImage,
        version_tag: str,
        arch: str,
        db: AsyncSession,
        triggered_by: str = "manual",
        *,
        provider: ResourceProvider | None = None,
    ) -> ImageVersion:
        """Trigger a GitLab pipeline to build an app image version."""
        if not image.gitlab_project_id:
            raise BadRequestError("App image has no GitLab project configured")

        if provider is None:
            provider = await self.get_default_instance(db)

        version = ImageVersion(
            image_type="app",
            app_image_id=image.id,
            version_tag=version_tag,
            arch=arch,
            status_flag=4,
            status_text="pending",
        )
        db.add(version)
        await db.flush()

        try:
            gl = self._get_client(provider)
            gl_project = gl.projects.get(image.gitlab_project_id)
            pipeline = gl_project.pipelines.create(
                {
                    "ref": "main",
                    "variables": [
                        {"key": "VERSION_TAG", "value": version_tag},
                        {"key": "TARGET_ARCH", "value": arch},
                        {"key": "IMAGE_VERSION_ID", "value": str(version.id)},
                    ],
                }
            )
        except gitlab.exceptions.GitlabError as e:
            version.status_flag = 1
            version.status_text = f"Failed to trigger pipeline: {e}"
            await db.commit()
            raise ExternalServiceError("GitLab", str(e)) from e

        base_url = self._pipeline_base_url(provider)
        now = datetime.now(UTC)
        build_log = BuildLog(
            image_version_id=version.id,
            pipeline_id=str(pipeline.id),
            pipeline_url=f"{base_url}/{image.gitlab_project_id}/-/pipelines/{pipeline.id}",
            status_flag=3,
            status_text="running",
            triggered_by=triggered_by,
            started_at=now,
        )
        db.add(build_log)

        version.status_flag = 3
        version.status_text = "running"

        await db.commit()
        await db.refresh(version)
        return version


# Module-level singleton (backward-compatible)
build_service = BuildService()
