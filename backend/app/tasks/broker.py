"""Taskiq broker: RedisStreamBroker over the infra Redis (single queue).

Worker entrypoint (smoke-tested in dev-stand):

    taskiq worker app.tasks.broker:broker

Broker defaults follow the ADR: ack after execution (at-least-once),
30 min idle timeout (must exceed max task duration or XAUTOCLAIM
duplicates long syncs), explicit unacknowledged_lock_timeout (None +
SIGKILLed worker hangs autoclaim forever), no result backend.
"""

from taskiq_redis import RedisStreamBroker

from app.config import settings

broker = RedisStreamBroker(
    url=settings.redis_url,
    queue_name="taskiq",
    idle_timeout=settings.task_idle_timeout_ms,
    unacknowledged_lock_timeout=60,
)
