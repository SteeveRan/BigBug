import re
from datetime import UTC, datetime

import gitlab
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ExternalServiceError
from app.models.gitlab_mirror import GitlabMirror
from app.models.sync_log import SyncLog
from app.models.sync_schedule import SyncSchedule


def _parse_gitlab_url(url: str) -> tuple[str, str]:
    """Parse GitLab URL and return (namespace, project_name)."""
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
    def _get_client(self) -> gitlab.Gitlab:
        gl = gitlab.Gitlab(settings.gitlab_url, private_token=settings.gitlab_token)
        return gl

    async def import_mirror_from_url(
        self, gitlab_url: str, project_id: int, db: AsyncSession
    ) -> GitlabMirror:
        """Import an existing GitLab project as a mirror."""
        try:
            gl = self._get_client()
            namespace, name = _parse_gitlab_url(gitlab_url)
            gl_project = gl.projects.get(f"{namespace}/{name}")
        except gitlab.exceptions.GitlabError as e:
            raise ExternalServiceError("GitLab", str(e))

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
            mirror_id=mirror.id,
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
    ) -> SyncLog:
        """Trigger a GitLab pipeline for mirror sync."""
        if not mirror.pipeline_trigger_token:
            raise BadRequestError("Mirror has no pipeline trigger token configured")

        try:
            gl = self._get_client()
            gl_project = gl.projects.get(mirror.gitlab_project_id)
            pipeline = gl_project.trigger_pipeline(
                mirror.mirrored_branch,
                mirror.pipeline_trigger_token,
            )
        except gitlab.exceptions.GitlabError as e:
            raise ExternalServiceError("GitLab", str(e))

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

    async def get_pipeline_status(self, mirror: GitlabMirror, pipeline_id: str) -> dict:
        """Poll pipeline status from GitLab."""
        try:
            gl = self._get_client()
            gl_project = gl.projects.get(mirror.gitlab_project_id)
            pipeline = gl_project.pipelines.get(int(pipeline_id))
            return {"status": pipeline.status, "id": pipeline.id}
        except gitlab.exceptions.GitlabError as e:
            raise ExternalServiceError("GitLab", str(e))


gitlab_service = GitLabService()
