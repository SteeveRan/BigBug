"""
@file reports.py
@description Pydantic schemas for mirroring reports — duplicates, storage,
             status, and syncs. Used by ReportsService and Reports API router.
@dependencies pydantic
@relatedFiles ../services/reports.py, ../api/reports.py, ../models/mirror.py
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════════════
# Duplicates Report
# ═══════════════════════════════════════════════════════════════════════════


class DuplicateMirrorItem(BaseModel):
    """Single mirror entry in a duplicate group."""

    mirror_id: int
    source_url: str
    target_gitlab_instance_name: str | None = None
    target_path: str | None = None
    status_flag: int
    status_text: str | None = None
    created_at: datetime
    sync_group_name: str | None = None


class DuplicateGroup(BaseModel):
    """A group of mirrors that share the same source_url."""

    source_url: str
    mirror_count: int
    mirrors: list[DuplicateMirrorItem]


class DuplicatesReport(BaseModel):
    """Full duplicates report response."""

    warning: str = Field(
        description="Human-readable summary, e.g. 'Обнаружено 3 группы дубликатов (всего 8 зеркал)'"
    )
    total_groups: int
    total_mirrors: int
    groups: list[DuplicateGroup]


# ═══════════════════════════════════════════════════════════════════════════
# Storage Report
# ═══════════════════════════════════════════════════════════════════════════


class MirrorStorageItem(BaseModel):
    """Storage usage for a single mirror."""

    mirror_id: int
    source_url: str
    target_gitlab_instance_name: str | None = None
    target_path: str | None = None
    sync_group_name: str | None = None
    repo_size_bytes: int | None = None
    history_size_bytes: int | None = None
    total_size_bytes: int | None = None
    error: str | None = Field(None, description="Error message if GitLab API was unreachable")
    accessible: bool = Field(
        True,
        description="Whether the GitLab project storage info was successfully retrieved",
    )


class StorageSummary(BaseModel):
    """Aggregated storage summary for a grouping key."""

    key: str
    repo_size_bytes: int = 0
    history_size_bytes: int = 0
    total_size_bytes: int = 0


class StorageReport(BaseModel):
    """Full storage report with per-mirror details and aggregations."""

    items: list[MirrorStorageItem]
    by_gitlab_instance: list[StorageSummary] = []
    by_sync_group: list[StorageSummary] = []
    grand_total: StorageSummary | None = None
    collected_at: datetime | None = Field(None, description="When storage data was last refreshed")
    is_stale: bool = Field(
        True, description="True if data is older than 24h and should be refreshed"
    )
    collection_status: str = Field(
        "complete",
        description="One of: 'idle' (not yet collected), 'in_progress', 'complete', 'error'",
    )


class StorageRefreshStatus(BaseModel):
    """Response after requesting a storage cache refresh."""

    collection_status: str
    message: str


# ═══════════════════════════════════════════════════════════════════════════
# Status Report
# ═══════════════════════════════════════════════════════════════════════════


class StatusCountItem(BaseModel):
    """Count of mirrors in a particular status."""

    status_flag: int
    status_text: str
    count: int

    # Pre-computed labels for frontend
    label: str = Field(
        description="Human-readable status label: OK, Failed, Warning, In Progress, Pending"
    )


class MirrorStatusItem(BaseModel):
    """Mirror with its current status for drill-down lists."""

    mirror_id: int
    source_url: str
    status_flag: int
    status_text: str | None = None
    target_path: str | None = None
    sync_group_name: str | None = None


class StatusReport(BaseModel):
    """Full status report with counts, trend, and drill-down lists."""

    status_counts: list[StatusCountItem]
    total_mirrors: int
    ok_mirrors: list[MirrorStatusItem] = []
    failed_mirrors: list[MirrorStatusItem] = []
    warning_mirrors: list[MirrorStatusItem] = []
    in_progress_mirrors: list[MirrorStatusItem] = []
    pending_mirrors: list[MirrorStatusItem] = []


# ═══════════════════════════════════════════════════════════════════════════
# Syncs Report
# ═══════════════════════════════════════════════════════════════════════════


class DailySyncsItem(BaseModel):
    """Sync counts for a single day."""

    date: str  # YYYY-MM-DD
    total: int
    successful: int
    failed: int
    stale: int  # mirrors detected as stale (status_flag=2 / Warning)


class SyncGroupSyncsItem(BaseModel):
    """Sync counts aggregated by sync group."""

    sync_group_name: str
    total: int
    successful: int
    failed: int
    stale: int


class TopSyncMirrorItem(BaseModel):
    """Mirror ranking entry (by sync count or error count)."""

    mirror_id: int
    source_url: str
    taget_path: str | None = None  # note: typo in schema spec — kept for consistency
    count: int


class SyncsReport(BaseModel):
    """Full syncs report over a date range."""

    period_start: str  # YYYY-MM-DD
    period_end: str  # YYYY-MM-DD
    daily: list[DailySyncsItem]
    by_sync_group: list[SyncGroupSyncsItem] = []
    top_by_syncs: list[TopSyncMirrorItem] = []
    top_by_errors: list[TopSyncMirrorItem] = []


# ═══════════════════════════════════════════════════════════════════════════
# Bulk Operation Schemas
# ═══════════════════════════════════════════════════════════════════════════


class BulkReassignSyncGroupRequest(BaseModel):
    """Request to reassign multiple mirrors to a different sync group."""

    mirror_ids: list[int] = Field(..., min_length=1, max_length=100)
    sync_group_id: int


class BulkChangeTargetGitlabRequest(BaseModel):
    """Request to change target GitLab instance for multiple mirrors.

    This reassigns mirrors to a SyncGroup that uses the desired GitLab instance
    (target GitLab is determined by SyncGroup → Pipeline → GitlabInstance).
    The mirrors' source repositories are retained.
    """

    mirror_ids: list[int] = Field(..., min_length=1, max_length=100)
    sync_group_id: int


class BulkApplyPipelineRequest(BaseModel):
    """Request to apply a Pipeline to multiple mirrors' SyncGroups."""

    mirror_ids: list[int] = Field(..., min_length=1, max_length=100)
    pipeline_id: int


class BulkOperationResultItem(BaseModel):
    """Result for a single mirror in a bulk operation."""

    mirror_id: int
    success: bool
    message: str | None = None


class BulkOperationResponse(BaseModel):
    """Response for any bulk operation."""

    operation: str
    total: int
    succeeded: int
    failed: int
    results: list[BulkOperationResultItem] = []
