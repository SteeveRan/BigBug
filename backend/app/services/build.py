"""
@file build.py
@description Build service — trigger GitLab pipelines for gold and app image
             builds. Supports multi-instance: resolves the active GitLab instance
             from the database; falls back to settings.GITLAB_URL /
             settings.GITLAB_TOKEN for backward compatibility.
@dependencies python-gitlab, app.config.settings, app.core.secrets,
               app.services.integrations.get_default_gitlab_instance
@relatedFiles ../models/gitlab_instance.py, ../models/gold_image.py,
               ../models/app_image.py, ./integrations.py, ./gitlab.py
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

if TYPE_CHECKING:
    from app.models.gitlab_instance import GitlabInstance


class BuildService:
    # ------------------------------------------------------------------
    # Instance resolution
    # ------------------------------------------------------------------

    @staticmethod
    async def get_default_instance(db: AsyncSession) -> GitlabInstance | None:
        """Return the first active GitLab instance from the database."""
        from app.services.integrations import get_default_gitlab_instance

        return await get_default_gitlab_instance(db)

    # ------------------------------------------------------------------
    # Client factory
    # ------------------------------------------------------------------

    def _get_client(self, instance: GitlabInstance | None = None) -> gitlab.Gitlab:
        """
        Build a python-gitlab client.

        Priority:
        1. ``instance`` — use its URL and *decrypted* token.
        2. ``settings.gitlab_url`` and ``settings.gitlab_token`` (fallback).
        3. ``settings.gitlab_url`` without auth.
        """
        if instance is not None:
            token = decrypt_secret(instance.token) if instance.token else None
            return gitlab.Gitlab(instance.url, private_token=token or None)

        # Backward-compatible fallback
        if settings.gitlab_url:
            return gitlab.Gitlab(
                settings.gitlab_url,
                private_token=settings.gitlab_token or None,
            )
        return gitlab.Gitlab()

    def _pipeline_base_url(self, instance: GitlabInstance | None) -> str:
        """Return the base URL for constructing pipeline links."""
        if instance is not None:
            return instance.url
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
        instance: GitlabInstance | None = None,
    ) -> ImageVersion:
        """Trigger a GitLab pipeline to build a gold image version."""
        if not image.gitlab_project_id:
            raise BadRequestError("Gold image has no GitLab project configured")

        if instance is None:
            instance = await self.get_default_instance(db)

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
            gl = self._get_client(instance)
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

        base_url = self._pipeline_base_url(instance)
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
        instance: GitlabInstance | None = None,
    ) -> ImageVersion:
        """Trigger a GitLab pipeline to build an app image version."""
        if not image.gitlab_project_id:
            raise BadRequestError("App image has no GitLab project configured")

        if instance is None:
            instance = await self.get_default_instance(db)

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
            gl = self._get_client(instance)
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

        base_url = self._pipeline_base_url(instance)
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
