from datetime import UTC

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.build_log import BuildLog
from app.models.docker_image_source import DockerImageSource
from app.models.docker_sync_log import DockerSyncLog
from app.models.helm_chart_source import HelmChartSource
from app.models.helm_sync_log import HelmSyncLog
from app.models.image_version import ImageVersion
from app.services import pipeline as pipeline_service
from app.services.audit import AuditService

router = APIRouter()

# Status flag mapping from GitLab pipeline status
GITLAB_STATUS_MAP = {
    "success": 0,
    "failed": 1,
    "warning": 2,
    "running": 3,
    "pending": 4,
    "created": 4,
    "canceled": 1,
    "skipped": 2,
}


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive GitLab pipeline webhook events."""
    payload = await request.json()

    object_kind = payload.get("object_kind")
    if object_kind != "pipeline":
        return {"status": "ignored", "reason": "not a pipeline event"}

    pipeline = payload.get("object_attributes", {})
    pipeline_id = str(pipeline.get("id", ""))
    pipeline_status = pipeline.get("status", "")
    pipeline_url = payload.get("project", {}).get("web_url", "") + f"/-/pipelines/{pipeline_id}"

    status_flag = GITLAB_STATUS_MAP.get(pipeline_status, 4)

    # Try to find matching BuildLog
    build_result = await db.execute(select(BuildLog).where(BuildLog.pipeline_id == pipeline_id))
    build_log = build_result.scalar_one_or_none()

    if build_log:
        build_log.status_flag = status_flag
        build_log.status_text = pipeline_status
        build_log.pipeline_url = pipeline_url
        if pipeline_status in ("success", "failed", "canceled"):
            from datetime import datetime

            build_log.finished_at = datetime.now(UTC)
            # Update parent ImageVersion status
            version_result = await db.execute(
                select(ImageVersion).where(ImageVersion.id == build_log.image_version_id)
            )
            version = version_result.scalar_one_or_none()
            if version:
                version.status_flag = status_flag
                version.status_text = pipeline_status
                if pipeline_status == "success":
                    version.built_at = datetime.now(UTC)
        await db.commit()
        return {"status": "ok", "type": "build_log", "id": build_log.id}

    # Try to find matching HelmSyncLog
    helm_result = await db.execute(
        select(HelmSyncLog).where(HelmSyncLog.pipeline_id == pipeline_id)
    )
    helm_sync_log = helm_result.scalar_one_or_none()

    if helm_sync_log:
        helm_sync_log.status_flag = status_flag  # type: ignore[assignment]
        helm_sync_log.status_text = pipeline_status  # type: ignore[assignment]
        helm_sync_log.pipeline_url = pipeline_url  # type: ignore[assignment]
        if pipeline_status in ("success", "failed", "canceled"):
            from datetime import datetime

            helm_sync_log.finished_at = datetime.now(UTC)  # type: ignore[assignment]

            # Update parent HelmChartSource status
            source_result = await db.execute(
                select(HelmChartSource).where(HelmChartSource.id == helm_sync_log.source_id)
            )
            source = source_result.scalar_one_or_none()
            if source:
                source.status_flag = status_flag  # type: ignore[assignment]
                source.status_text = pipeline_status  # type: ignore[assignment]
                if pipeline_status == "success":
                    source.last_synced_at = datetime.now(UTC)  # type: ignore[assignment]

        await db.commit()
        return {"status": "ok", "type": "helm_sync_log", "id": helm_sync_log.id}

    # Try to find matching DockerSyncLog
    docker_result = await db.execute(
        select(DockerSyncLog).where(DockerSyncLog.pipeline_id == pipeline_id)
    )
    docker_sync_log = docker_result.scalar_one_or_none()

    if docker_sync_log:
        docker_sync_log.status_flag = status_flag  # type: ignore[assignment]
        docker_sync_log.status_text = pipeline_status  # type: ignore[assignment]
        docker_sync_log.pipeline_url = pipeline_url  # type: ignore[assignment]
        if pipeline_status in ("success", "failed", "canceled"):
            from datetime import datetime

            docker_sync_log.finished_at = datetime.now(UTC)  # type: ignore[assignment]

            # Update parent DockerImageSource status
            source_result = await db.execute(
                select(DockerImageSource).where(DockerImageSource.id == docker_sync_log.source_id)
            )
            source = source_result.scalar_one_or_none()
            if source:
                source.status_flag = status_flag  # type: ignore[assignment]
                source.status_text = pipeline_status  # type: ignore[assignment]
                if pipeline_status == "success":
                    source.last_synced_at = datetime.now(UTC)  # type: ignore[assignment]

        await db.commit()
        return {"status": "ok", "type": "docker_sync_log", "id": docker_sync_log.id}

    # Try to find matching PipelineRun
    pipeline_run = await pipeline_service.update_pipeline_status(
        db,
        gitlab_pipeline_id=int(pipeline_id),
        status=pipeline_status,
        web_url=pipeline_url,
        duration=pipeline.get("duration"),
    )

    if pipeline_run:
        # Check if this PipelineRun is associated with any MirrorLogs
        # and log audit events for mirror sync completion/failure
        if pipeline_status in ("success", "failed", "canceled"):
            from app.models.mirror_log import MirrorLog

            mirror_result = await db.execute(
                select(MirrorLog).where(MirrorLog.pipeline_run_id == pipeline_run.id)
            )
            mirror_log = mirror_result.scalar_one_or_none()
            if mirror_log is not None:
                from app.models.mirror import Mirror

                mirror_obj_result = await db.execute(
                    select(Mirror).where(Mirror.id == mirror_log.mirror_id)
                )
                mirror_obj = mirror_obj_result.scalar_one_or_none()
                if mirror_obj is not None:
                    if pipeline_status == "success":
                        audit_action = "mirror.sync_completed"
                    else:
                        audit_action = "mirror.sync_failed"

                    await AuditService.log_event(
                        db,
                        user_id=None,
                        username="system",
                        action=audit_action,
                        resource_type="mirror",
                        resource_id=mirror_obj.id,
                        resource_name=mirror_obj.target_project_name,
                        details={
                            "pipeline_run_id": pipeline_run.id,
                            "gitlab_pipeline_id": pipeline_run.gitlab_pipeline_id,
                            "pipeline_status": pipeline_status,
                            "mirror_log_id": mirror_log.id,
                        },
                    )
                    await db.commit()

        return {"status": "ok", "type": "pipeline_run", "id": pipeline_run.id}

    return {"status": "ignored", "reason": "no matching log found for pipeline_id"}
