from datetime import UTC, datetime

import gitlab
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import BadRequestError, ExternalServiceError
from app.models.app_image import AppImage
from app.models.build_log import BuildLog
from app.models.gold_image import GoldImage
from app.models.image_version import ImageVersion


class BuildService:
    def _get_gitlab_client(self) -> gitlab.Gitlab:
        return gitlab.Gitlab(settings.gitlab_url, private_token=settings.gitlab_token)

    async def trigger_gold_build(
        self,
        image: GoldImage,
        version_tag: str,
        arch: str,
        db: AsyncSession,
        triggered_by: str = "manual",
    ) -> ImageVersion:
        """Trigger a GitLab pipeline to build a gold image version."""
        if not image.gitlab_project_id:
            raise BadRequestError("Gold image has no GitLab project configured")

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
            gl = self._get_gitlab_client()
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
            raise ExternalServiceError("GitLab", str(e))

        now = datetime.now(UTC)
        build_log = BuildLog(
            image_version_id=version.id,
            pipeline_id=str(pipeline.id),
            pipeline_url=f"{settings.gitlab_url}/{image.gitlab_project_id}/-/pipelines/{pipeline.id}",
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
    ) -> ImageVersion:
        """Trigger a GitLab pipeline to build an app image version."""
        if not image.gitlab_project_id:
            raise BadRequestError("App image has no GitLab project configured")

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
            gl = self._get_gitlab_client()
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
            raise ExternalServiceError("GitLab", str(e))

        now = datetime.now(UTC)
        build_log = BuildLog(
            image_version_id=version.id,
            pipeline_id=str(pipeline.id),
            pipeline_url=f"{settings.gitlab_url}/{image.gitlab_project_id}/-/pipelines/{pipeline.id}",
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


build_service = BuildService()
