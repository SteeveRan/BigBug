"""Import task modules so the taskiq worker process registers their bodies.

The worker entrypoint loads only ``app.tasks.broker``; without these imports
enqueued tasks resolve to "task not found" and get acked unexecuted.
"""

from app.tasks import metadata_tasks, sync_tasks  # noqa: F401
