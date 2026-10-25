"""Sync-runs admin API (issue #112): operational view of tracked task runs
plus recovery actions (retry / requeue). The DLQ is a table filter
(``status=failed_permanent``), not a dead stream.

All actions re-enqueue through the standard ``enqueue()`` helper — no direct
broker calls from the API (ADR-0039) — and write an audit event (ADR-0026).
Gated by ``system:config`` like the other operational admin endpoints.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.database import get_db
from app.models.sync_run import SyncRun
from app.models.user import User
from app.schemas.sync_run import SyncRunOut
from app.services.audit import AuditService
from app.tasks.enqueue import enqueue
from app.tasks.run_tracking import _resolve_task, is_stuck

logger = logging.getLogger(__name__)

router = APIRouter()

# Recoverable statuses for the DLQ filter / retry actions.
RECOVERABLE = ("failed", "failed_permanent")


def _to_out(run: SyncRun) -> SyncRunOut:
    return SyncRunOut(
        id=run.id,
        task_name=run.task_name,
        entity_type=run.entity_type,
        entity_id=run.entity_id,
        status=run.status,
        attempts=run.attempts,
        max_attempts=run.max_attempts,
        payload=run.payload,
        heartbeat_at=run.heartbeat_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
        created_at=run.created_at,
        stuck=is_stuck(run.status, run.heartbeat_at, run.created_at),
    )


async def _get_run(db: AsyncSession, run_id: int) -> SyncRun:
    result = await db.execute(select(SyncRun).where(SyncRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sync run not found")
    return run


async def _reenqueue(run: SyncRun) -> None:
    """Re-enqueue the original task via the standard enqueue path."""
    task = _resolve_task(run.task_name)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Unknown task '{run.task_name}' — cannot re-enqueue",
        )
    payload = run.payload or {}
    await enqueue(
        task,
        *(payload.get("args") or []),
        entity_type=run.entity_type,
        entity_id=run.entity_id,
        **(payload.get("kwargs") or {}),
    )


async def _audit(
    request: Request,
    user: User,
    db: AsyncSession,
    action: str,
    run: SyncRun,
    details: dict | None = None,
) -> None:
    await AuditService.log_event(
        db,
        user_id=user.id,
        username=user.username,
        action=action,
        resource_type="sync_run",
        resource_id=run.id,
        resource_name=run.task_name,
        details=details,
        ip_address=request.client.host if request.client else None,
    )


@router.get("", response_model=list[SyncRunOut])
async def list_sync_runs(
    run_status: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    stuck: bool = False,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_permission("system:config")),
):
    """List tracked sync runs. ``run_status`` filters by exact status
    (``failed_permanent`` = DLQ); ``stuck=true`` shows only running runs with
    a stale heartbeat."""
    query = select(SyncRun).order_by(SyncRun.id.desc())
    if run_status:
        query = query.where(SyncRun.status == run_status)
    if entity_type:
        query = query.where(SyncRun.entity_type == entity_type)
    if entity_id is not None:
        query = query.where(SyncRun.entity_id == entity_id)
    result = await db.execute(query)
    runs = result.scalars().all()
    if stuck:
        runs = [r for r in runs if is_stuck(r.status, r.heartbeat_at, r.created_at)]
    return [_to_out(r) for r in runs]


@router.post("/{run_id}/retry", response_model=SyncRunOut)
async def retry_sync_run(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system:config")),
):
    """Re-enqueue a failed/failed_permanent run through the standard path."""
    run = await _get_run(db, run_id)
    if run.status not in RECOVERABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Run status '{run.status}' is not retryable",
        )
    await _reenqueue(run)
    await _audit(request, current_user, db, "retry", run)
    return _to_out(run)


@router.post("/retry-all-failed", response_model=dict)
async def retry_all_failed(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system:config")),
):
    """Re-enqueue every failed_permanent run (drain the DLQ)."""
    result = await db.execute(select(SyncRun).where(SyncRun.status == "failed_permanent"))
    runs = result.scalars().all()
    retried = 0
    for run in runs:
        try:
            await _reenqueue(run)
        except HTTPException:
            logger.exception("Cannot re-enqueue sync_run %d (task %s)", run.id, run.task_name)
            continue
        await _audit(request, current_user, db, "retry", run, details={"batch": "retry-all-failed"})
        retried += 1
    return {"retried": retried, "total_failed_permanent": len(runs)}


@router.post("/{run_id}/requeue", response_model=SyncRunOut)
async def requeue_sync_run(
    run_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("system:config")),
):
    """Requeue a stuck run (running with a stale heartbeat, or a phantom
    queued row after a broker outage): the old row is marked superseded and
    the task is re-enqueued fresh."""
    run = await _get_run(db, run_id)
    if not is_stuck(run.status, run.heartbeat_at, run.created_at):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only stuck runs (running with stale heartbeat) can be requeued",
        )
    run.status = "superseded"
    await db.commit()
    await _reenqueue(run)
    await _audit(request, current_user, db, "requeue", run)
    return _to_out(run)
