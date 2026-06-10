"""
@file gitlab.py
@description GitLab mirror service — import projects, trigger sync pipelines,
             and poll pipeline status. Supports multi-instance: accepts an
             optional ``instance`` parameter; falls back to the first active
             DB instance, then to settings.GITLAB_URL / settings.GITLAB_TOKEN
             for backward compatibility.
@dependencies python-gitlab, app.config.settings, app.core.secrets,
              app.services.integrations.get_default_gitlab_instance
@relatedFiles ../models/gitlab_instance.py, ../models/gitlab_mirror.py,
              ../core/secrets.py, ./integrations.py
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import gitlab
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ExternalServiceError
from app.core.secrets import decrypt_secret
from app.models.gitlab_mirror import GitlabMirror
from app.models.sync_log import SyncLog
from app.models.sync_schedule import SyncSchedule

if TYPE_CHECKING:
    from app.models.gitlab_instance import GitlabInstance


def _parse_gitlab_url(url: str) -> tuple[str, str]:
    """Parse a GitLab URL and return (namespace, project_name)."""
    patterns = [
        r"gitlab[^/]*/([^/]+/[^/\.]+?)(?:\.git)?$",
        r"([^/]+/[^/\.]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            parts = match.group(1).split("/")
            if len(parts) >= 2:
                return "/".join(parts[:-1]), parts[-1]
    raise BadRequestError(f"Cannot parse GitLab URL: {url}")


class GitLabService:
    """Service for interacting with GitLab instances."""

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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def import_mirror_from_url(
        self,
        gitlab_url: str,
        project_id: int,
        db: AsyncSession,
        *,
        instance: GitlabInstance | None = None,
    ) -> GitlabMirror:
        """Import an existing GitLab project as a mirror."""
        if instance is None:
            instance = await self.get_default_instance(db)

        try:
            gl = self._get_client(instance)
            namespace, name = _parse_gitlab_url(gitlab_url)
            gl_project = gl.projects.get(f"{namespace}/{name}")
        except gitlab.exceptions.GitlabError as e:
            raise ExternalServiceError("GitLab", str(e)) from e

        mirror = GitlabMirror(
            project_id=project_id,
            gitlab_project_id=str(gl_project.id),
            gitlab_namespace=gl_project.namespace["full_path"],
            gitlab_url=gl_project.web_url,
            gitlab_name=gl_project.name,
            is_imported=True,
            status_flag=4,
        )
        db.add(mirror)
        await db.flush()

        # Create default sync schedule
        schedule = SyncSchedule(
            sync_type="git_mirror",
            git_mirror_id=mirror.id,
            is_enabled=True,
            use_default_schedule=True,
        )
        db.add(schedule)

        await db.commit()
        await db.refresh(mirror)
        return mirror

    async def trigger_sync(
        self,
        mirror: GitlabMirror,
        db: AsyncSession,
        triggered_by: str = "manual",
        *,
        instance: GitlabInstance | None = None,
    ) -> SyncLog:
        """Trigger a GitLab pipeline for mirror sync."""
        if not mirror.pipeline_trigger_token:
            raise BadRequestError("Mirror has no pipeline trigger token configured")

        if instance is None:
            instance = await self.get_default_instance(db)

        try:
            gl = self._get_client(instance)
            gl_project = gl.projects.get(mirror.gitlab_project_id)
            pipeline = gl_project.trigger_pipeline(
                mirror.mirrored_branch,
                mirror.pipeline_trigger_token,
            )
        except gitlab.exceptions.GitlabError as e:
            raise ExternalServiceError("GitLab", str(e)) from e

        now = datetime.now(UTC)
        sync_log = SyncLog(
            mirror_id=mirror.id,
            pipeline_id=str(pipeline.id),
            pipeline_url=f"{mirror.gitlab_url}/-/pipelines/{pipeline.id}",
            status_flag=3,  # in_progress
            status_text="running",
            triggered_by=triggered_by,
            started_at=now,
        )
        db.add(sync_log)

        mirror.status_flag = 3
        mirror.status_text = "sync in progress"

        await db.commit()
        await db.refresh(sync_log)
        return sync_log

    async def get_pipeline_status(
        self,
        mirror: GitlabMirror,
        pipeline_id: str,
        *,
        instance: GitlabInstance | None = None,
        db: AsyncSession | None = None,
    ) -> dict:
        """Poll pipeline status from GitLab."""
        if instance is None and db is not None:
            instance = await self.get_default_instance(db)

        try:
            gl = self._get_client(instance)
            gl_project = gl.projects.get(mirror.gitlab_project_id)
            pipeline = gl_project.pipelines.get(int(pipeline_id))
            return {"status": pipeline.status, "id": pipeline.id}
        except gitlab.exceptions.GitlabError as e:
            raise ExternalServiceError("GitLab", str(e)) from e


# Module-level singleton (backward-compatible)
gitlab_service = GitLabService()
