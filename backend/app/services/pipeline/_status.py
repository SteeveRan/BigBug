"""Status flag constants and GitLab status mapping for pipelines."""

STATUS_OK = 0
STATUS_FAILED = 1
STATUS_WARNING = 2
STATUS_IN_PROGRESS = 3
STATUS_PENDING = 4

GITLAB_STATUS_MAP: dict[str, int] = {
    "success": STATUS_OK,
    "failed": STATUS_FAILED,
    "warning": STATUS_WARNING,
    "running": STATUS_IN_PROGRESS,
    "pending": STATUS_PENDING,
    "created": STATUS_PENDING,
    "canceled": STATUS_FAILED,
    "skipped": STATUS_WARNING,
}


def _status_text(flag: int) -> str:
    """Map a status flag integer to its human-readable label."""
    return {0: "OK", 1: "Failed", 2: "Warning", 3: "Running", 4: "Pending"}.get(flag, "Unknown")
