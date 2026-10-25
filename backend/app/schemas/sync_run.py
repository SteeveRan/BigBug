"""
@file sync_run.py
@description Pydantic schemas for the sync-runs admin API (issue #112).
@dependencies pydantic
@relatedFiles ../api/sync_runs.py, ../models/sync_run.py
"""

from datetime import datetime

from pydantic import BaseModel


class SyncRunOut(BaseModel):
    id: int
    task_name: str
    entity_type: str | None
    entity_id: int | None
    status: str
    attempts: int
    max_attempts: int
    payload: dict | None
    heartbeat_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    created_at: datetime | None
    stuck: bool
