"""Outbox taskiq tasks (ADR-0039 Phase 3, issue #111).

``send_pending_outbox_task`` — batch-deliver unsent outbox rows to the
in-app sink (audit-log-style events), marking each row sent in the same
transaction as the delivery effect. Idempotency: a re-delivered task skips
rows already ``sent_at``-marked; the unique ``dedup_key`` prevents duplicate
rows at write time. The sink is pluggable — Phase 4 may add external
channels without touching the outbox contract.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.notification_outbox import NotificationOutbox
from app.services.audit import AuditService
from app.tasks.broker import broker
from app.tasks.run_tracking import run_tracked

logger = logging.getLogger(__name__)

_TASK_LABELS = {
    "max_retries": settings.task_max_retries,
    "ack_type": settings.task_ack_type,
}

BATCH_SIZE = 100

__all__ = ["send_pending_outbox_task"]


@broker.task(**_TASK_LABELS)
async def send_pending_outbox_task(batch_size: int = BATCH_SIZE) -> int:
    """Deliver unsent outbox rows to the in-app sink; return rows delivered.

    Delivery effect = audit-log event row; ``sent_at`` is stamped in the same
    transaction. A crash mid-batch costs the remaining rows only (per-row
    commit, same pattern as commit_cursor); a redelivered task skips rows
    already marked sent, and the unique dedup_key blocks duplicate rows.
    """

    async def _body() -> int:
        delivered = 0
        while True:
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(NotificationOutbox)
                    .where(NotificationOutbox.sent_at.is_(None))
                    .order_by(NotificationOutbox.created_at.asc(), NotificationOutbox.id.asc())
                    .limit(batch_size)
                )
                rows = result.scalars().all()
                if not rows:
                    break

                for row in rows:
                    await AuditService.log_event(
                        db,
                        user_id=None,
                        username="outbox",
                        action=row.event_type,
                        resource_type="notification",
                        resource_id=row.id,
                        details=row.payload,
                    )
                    row.sent_at = datetime.now(UTC)
                    await db.commit()
                    delivered += 1

                if len(rows) < batch_size:
                    break

        if delivered:
            logger.info("Outbox sender delivered %d notification(s)", delivered)
        return delivered

    return await run_tracked("send_pending_outbox_task", _body, payload={"args": [], "kwargs": {}})
