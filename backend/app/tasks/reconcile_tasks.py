"""Reconciliation taskiq task (ADR-0039 Phase 3, issue #111).

Thin body per the sync-engine skill: resolves arguments, delegates to
``app.services.reconciliation``, records outcome in logs. Enqueued by the
APScheduler cron (enqueue-only, job-pass lock) or the admin API.
"""

import logging

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.docker_image_source import DockerImageSource
from app.tasks.broker import broker
from app.tasks.run_tracking import run_tracked

logger = logging.getLogger(__name__)

_TASK_LABELS = {
    "max_retries": settings.task_max_retries,
    "ack_type": settings.task_ack_type,
}

__all__ = ["reconcile_docker_source_task", "reconcile_all_task"]


@broker.task(**_TASK_LABELS)
async def reconcile_docker_source_task(source_id: int) -> dict:
    """Reconcile one DockerImageSource against its target registry."""
    from app.services.reconciliation import reconcile_docker_source

    async def _body() -> dict:
        async with AsyncSessionLocal() as db:
            return await reconcile_docker_source(db, source_id)

    return await run_tracked(
        "reconcile_docker_source_task",
        _body,
        entity_type="docker_image_source",
        entity_id=source_id,
        payload={"args": [source_id], "kwargs": {}},
    )


@broker.task(**_TASK_LABELS)
async def reconcile_all_task() -> list[dict]:
    """Reconcile every DockerImageSource (cron pass body)."""
    from app.services.reconciliation import reconcile_docker_source

    async def _body() -> list[dict]:
        summaries: list[dict] = []
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(DockerImageSource))
            sources = result.scalars().all()

        for source in sources:
            async with AsyncSessionLocal() as db:
                try:
                    summaries.append(await reconcile_docker_source(db, source.id))
                except Exception:
                    logger.exception("Reconcile pass failed for source %d", source.id)
        return summaries

    return await run_tracked("reconcile_all_task", _body, payload={"args": [], "kwargs": {}})
