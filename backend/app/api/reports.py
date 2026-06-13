"""
@file reports.py
@description REST API for mirroring reports — duplicates, storage, status, syncs,
             and export endpoints. Admin-only access via `reports:read` permission.
@dependencies app.services.reports, app.core.rbac, app.schemas.reports
@relatedFiles ../services/reports.py, ../schemas/reports.py, ../../core/rbac.py
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permission
from app.database import get_db
from app.schemas.reports import (
    BulkApplyPipelineRequest,
    BulkChangeTargetGitlabRequest,
    BulkOperationResponse,
    BulkReassignSyncGroupRequest,
    DuplicatesReport,
    StatusReport,
    StorageRefreshStatus,
    StorageReport,
    SyncsReport,
)
from app.services.reports import ReportsService

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
# Helper: CSV serialization for reports
# ═══════════════════════════════════════════════════════════════════════════


def _csv_response(data: str, filename: str) -> Response:
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _json_response(data: str, filename: str) -> Response:
    return Response(
        content=data,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _serialize_duplicates_csv(report: DuplicatesReport) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "group_source_url",
            "mirror_id",
            "source_url",
            "target_gitlab",
            "target_path",
            "status_flag",
            "status_text",
            "sync_group_name",
            "created_at",
        ]
    )
    for group in report.groups:
        for item in group.mirrors:
            writer.writerow(
                [
                    group.source_url,
                    item.mirror_id,
                    item.source_url,
                    item.target_gitlab_instance_name or "",
                    item.target_path or "",
                    item.status_flag,
                    item.status_text or "",
                    item.sync_group_name or "",
                    item.created_at.isoformat() if item.created_at else "",
                ]
            )
    return output.getvalue()


def _serialize_storage_csv(report: StorageReport) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "mirror_id",
            "source_url",
            "target_gitlab",
            "target_path",
            "sync_group_name",
            "repo_size_bytes",
            "history_size_bytes",
            "total_size_bytes",
            "error",
            "accessible",
        ]
    )
    for item in report.items:
        writer.writerow(
            [
                item.mirror_id,
                item.source_url,
                item.target_gitlab_instance_name or "",
                item.target_path or "",
                item.sync_group_name or "",
                item.repo_size_bytes or 0,
                item.history_size_bytes or 0,
                item.total_size_bytes or 0,
                item.error or "",
                item.accessible,
            ]
        )
    return output.getvalue()


def _serialize_status_csv(report: StatusReport) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["mirror_id", "source_url", "status_flag", "status_text", "target_path", "sync_group_name"]
    )
    for bucket in [
        report.ok_mirrors,
        report.failed_mirrors,
        report.warning_mirrors,
        report.in_progress_mirrors,
        report.pending_mirrors,
    ]:
        for item in bucket:
            writer.writerow(
                [
                    item.mirror_id,
                    item.source_url,
                    item.status_flag,
                    item.status_text or "",
                    item.target_path or "",
                    item.sync_group_name or "",
                ]
            )
    return output.getvalue()


def _serialize_syncs_csv(report: SyncsReport) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "total", "successful", "failed", "stale"])
    for item in report.daily:
        writer.writerow([item.date, item.total, item.successful, item.failed, item.stale])
    return output.getvalue()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Duplicates Report
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/duplicates", response_model=DuplicatesReport)
async def get_duplicates_report(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
) -> DuplicatesReport:
    """Report on duplicate mirrors (same source_url mirrored multiple times)."""
    return await ReportsService.report_duplicates(db)


@router.get("/duplicates/export")
async def export_duplicates_report(
    format: str = Query("csv", pattern="^(csv|json)$"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
):
    """Export duplicates report as CSV or JSON."""
    report = await ReportsService.report_duplicates(db)
    if format == "csv":
        csv_data = _serialize_duplicates_csv(report)
        return _csv_response(csv_data, "duplicates_report.csv")
    else:
        json_data = report.model_dump_json(indent=2)
        return _json_response(json_data, "duplicates_report.json")


# ═══════════════════════════════════════════════════════════════════════════
# 2. Storage Report
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/storage", response_model=StorageReport)
async def get_storage_report(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
) -> StorageReport:
    """Report on disk space used by mirrored GitLab projects."""
    return await ReportsService.report_storage(db)


@router.post("/storage/refresh", response_model=StorageRefreshStatus)
async def refresh_storage_cache(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
) -> StorageRefreshStatus:
    """Force-refresh the storage cache from GitLab API."""
    report = await ReportsService.refresh_storage(db)
    return StorageRefreshStatus(
        collection_status=report.collection_status,
        message="Storage data refreshed from GitLab API",
    )


@router.get("/storage/export")
async def export_storage_report(
    format: str = Query("csv", pattern="^(csv|json)$"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
):
    """Export storage report as CSV or JSON."""
    report = await ReportsService.report_storage(db)
    if format == "csv":
        csv_data = _serialize_storage_csv(report)
        return _csv_response(csv_data, "storage_report.csv")
    else:
        json_data = report.model_dump_json(indent=2)
        return _json_response(json_data, "storage_report.json")


# ═══════════════════════════════════════════════════════════════════════════
# 3. Status Report
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/status", response_model=StatusReport)
async def get_status_report(
    trend_days: int = Query(0, ge=0, le=90, description="Trend window: 7, 30, or 90 days"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
) -> StatusReport:
    """Report on mirror status distribution (OK / Failed / Warning / In Progress / Pending)."""
    return await ReportsService.report_status(db, trend_days=trend_days)


@router.get("/status/export")
async def export_status_report(
    format: str = Query("csv", pattern="^(csv|json)$"),
    trend_days: int = Query(0, ge=0, le=90),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
):
    """Export status report as CSV or JSON."""
    report = await ReportsService.report_status(db, trend_days=trend_days)
    if format == "csv":
        csv_data = _serialize_status_csv(report)
        return _csv_response(csv_data, "status_report.csv")
    else:
        json_data = report.model_dump_json(indent=2)
        return _json_response(json_data, "status_report.json")


# ═══════════════════════════════════════════════════════════════════════════
# 4. Syncs Report
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/syncs", response_model=SyncsReport)
async def get_syncs_report(
    period_start: date | None = Query(
        None, description="Start date (YYYY-MM-DD). Default: 30 days ago"
    ),
    period_end: date | None = Query(None, description="End date (YYYY-MM-DD). Default: today"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
) -> SyncsReport:
    """Report on sync activity over a date range."""
    return await ReportsService.report_syncs(db, period_start=period_start, period_end=period_end)


@router.get("/syncs/export")
async def export_syncs_report(
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    format: str = Query("csv", pattern="^(csv|json)$"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
):
    """Export syncs report as CSV or JSON."""
    report = await ReportsService.report_syncs(db, period_start=period_start, period_end=period_end)
    if format == "csv":
        csv_data = _serialize_syncs_csv(report)
        return _csv_response(csv_data, "syncs_report.csv")
    else:
        json_data = report.model_dump_json(indent=2)
        return _json_response(json_data, "syncs_report.json")


# ═══════════════════════════════════════════════════════════════════════════
# 5. Bulk Operations
# ═══════════════════════════════════════════════════════════════════════════


@router.post("/bulk/reassign-sync-group", response_model=BulkOperationResponse)
async def bulk_reassign_sync_group(
    data: BulkReassignSyncGroupRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
) -> BulkOperationResponse:
    """Mass reassign mirrors to a different SyncGroup."""
    return await ReportsService.bulk_reassign_sync_group(db, data)


@router.post("/bulk/change-target-gitlab", response_model=BulkOperationResponse)
async def bulk_change_target_gitlab(
    data: BulkChangeTargetGitlabRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
) -> BulkOperationResponse:
    """Mass change target GitLab instance by reassigning mirrors to a SyncGroup."""
    return await ReportsService.bulk_change_target_gitlab(db, data)


@router.post("/bulk/apply-pipeline", response_model=BulkOperationResponse)
async def bulk_apply_pipeline(
    data: BulkApplyPipelineRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_permission("reports:read")),
) -> BulkOperationResponse:
    """Mass apply a Pipeline to mirrors' SyncGroups."""
    return await ReportsService.bulk_apply_pipeline(db, data)
