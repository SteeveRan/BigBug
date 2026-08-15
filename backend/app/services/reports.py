"""
@file reports.py
@description ReportsService — generates 4 types of mirroring reports:
             duplicates, storage, status, and syncs. All reports are generated
             on-the-fly from the database and (for storage) GitLab API.
@dependencies sqlalchemy, app.models.*, app.services.gitlab, app.schemas.reports
@relatedFiles ../api/reports.py, ../schemas/reports.py, ../models/mirror.py
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.mirror import Mirror
from app.models.mirror_log import MirrorLog, MirrorLogType
from app.models.pipeline import Pipeline as PipelineModel
from app.models.resource_provider import ResourceProvider
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.schemas.reports import (
    BulkApplyPipelineRequest,
    BulkChangeTargetGitlabRequest,
    BulkOperationResponse,
    BulkOperationResultItem,
    BulkReassignSyncGroupRequest,
    DailySyncsItem,
    DuplicateGroup,
    DuplicateMirrorItem,
    DuplicatesReport,
    MirrorStatusItem,
    MirrorStorageItem,
    StatusCountItem,
    StatusReport,
    StorageReport,
    StorageSummary,
    SyncGroupSyncsItem,
    SyncsReport,
    TopSyncMirrorItem,
)
from app.services.gitlab import GitLabService

logger = logging.getLogger(__name__)

# ── Status constants ──────────────────────────────────────────────────────
STATUS_OK = 0
STATUS_FAILED = 1
STATUS_WARNING = 2
STATUS_IN_PROGRESS = 3
STATUS_PENDING = 4

STATUS_LABELS: dict[int, str] = {
    STATUS_OK: "OK",
    STATUS_FAILED: "Failed",
    STATUS_WARNING: "Warning",
    STATUS_IN_PROGRESS: "In Progress",
    STATUS_PENDING: "Pending",
}

# ── In-memory storage cache (per-process) ─────────────────────────────────
_storage_cache: dict[str, Any] = {
    "items": [],
    "by_gitlab_instance": [],
    "by_sync_group": [],
    "grand_total": None,
    "collected_at": None,
    "collection_status": "idle",
}

STORAGE_CACHE_TTL = timedelta(hours=24)


def _source_url_from_repo(repo: SourceRepository) -> str:
    """Extract a usable source URL from a SourceRepository."""
    return repo.clone_url_https or repo.web_url or repo.full_name


def _derive_target_path(target_namespace: str | None, target_project_name: str | None) -> str:
    """Derive the full target path from namespace and project name."""
    ns = (target_namespace or "").strip("/")
    name = target_project_name or ""
    return f"{ns}/{name}" if ns else name


# ═══════════════════════════════════════════════════════════════════════════
# ReportsService
# ═══════════════════════════════════════════════════════════════════════════


class ReportsService:
    """Service that generates mirroring reports from database and external APIs."""

    # ........................................................................
    # Helpers
    # ........................................................................

    @staticmethod
    async def _get_all_active_mirrors(db: AsyncSession) -> list[Mirror]:
        """Fetch all non-deleted mirrors with eager-loaded relationships."""
        result = await db.execute(
            select(Mirror)
            .options(
                selectinload(Mirror.source_repository),
                selectinload(Mirror.sync_group)
                .selectinload(SyncGroup.pipeline)
                .selectinload(PipelineModel.provider)
                .selectinload(ResourceProvider.credential),
            )
            .where(~Mirror.is_deleted)
            .order_by(Mirror.id)
        )
        return list(result.unique().scalars().all())

    @staticmethod
    def _status_text(flag: int) -> str:
        return STATUS_LABELS.get(flag, "Unknown")

    # ........................................................................
    # 1. Duplicates Report
    # ........................................................................

    @staticmethod
    async def report_duplicates(db: AsyncSession) -> DuplicatesReport:
        """
        Group mirrors by source_url and report those with >1 mirror.

        Only considers non-deleted mirrors.
        """
        mirrors = await ReportsService._get_all_active_mirrors(db)

        # Group by source_url
        url_map: dict[str, list[Mirror]] = defaultdict(list)
        for m in mirrors:
            sr = m.source_repository
            if sr is None:
                continue
            url = _source_url_from_repo(sr)
            url_map[url].append(m)

        # Filter to groups with >1 mirror
        duplicate_groups: list[DuplicateGroup] = []
        total_dup_mirrors = 0
        for url, group in sorted(url_map.items()):
            if len(group) <= 1:
                continue
            total_dup_mirrors += len(group)
            items = [
                DuplicateMirrorItem(
                    mirror_id=m.id,
                    source_url=url,
                    target_gitlab_instance_name=(
                        m.target_gitlab_instance.name if m.target_gitlab_instance else None
                    ),
                    target_path=_derive_target_path(m.target_namespace, m.target_project_name),
                    status_flag=m.status_flag,
                    status_text=m.status_text,
                    created_at=m.created_at,
                    sync_group_name=m.sync_group.name if m.sync_group else None,
                )
                for m in sorted(group, key=lambda x: x.id)
            ]
            duplicate_groups.append(
                DuplicateGroup(
                    source_url=url,
                    mirror_count=len(group),
                    mirrors=items,
                )
            )

        return DuplicatesReport(
            warning=(
                f"Обнаружено {len(duplicate_groups)} групп дубликатов "
                f"(всего {total_dup_mirrors} зеркал)"
            ),
            total_groups=len(duplicate_groups),
            total_mirrors=total_dup_mirrors,
            groups=duplicate_groups,
        )

    # ........................................................................
    # 2. Storage Report
    # ........................................................................

    @staticmethod
    async def report_storage(
        db: AsyncSession,
        force_refresh: bool = False,
    ) -> StorageReport:
        """
        Report on storage usage per mirror, aggregated by GitLab instance
        and SyncGroup.

        Uses a per-process in-memory cache with 24h TTL. Pass
        ``force_refresh=True`` to bypass the cache and collect fresh data.
        """
        global _storage_cache

        now = datetime.now(UTC)

        # Check cache freshness
        cache_fresh = False
        if (
            not force_refresh
            and _storage_cache["collected_at"] is not None
            and _storage_cache["collection_status"] == "complete"
        ):
            age = now - _storage_cache["collected_at"]
            if age < STORAGE_CACHE_TTL:
                cache_fresh = True

        if cache_fresh:
            return StorageReport(
                items=_storage_cache["items"],
                by_gitlab_instance=_storage_cache["by_gitlab_instance"],
                by_sync_group=_storage_cache["by_sync_group"],
                grand_total=_storage_cache["grand_total"],
                collected_at=_storage_cache["collected_at"],
                is_stale=False,
                collection_status="complete",
            )

        # If collection is already in progress, return current stale state
        if _storage_cache["collection_status"] == "in_progress" and not force_refresh:
            return StorageReport(
                items=_storage_cache.get("items", []),
                by_gitlab_instance=_storage_cache.get("by_gitlab_instance", []),
                by_sync_group=_storage_cache.get("by_sync_group", []),
                grand_total=_storage_cache.get("grand_total"),
                collected_at=_storage_cache.get("collected_at"),
                is_stale=True,
                collection_status="in_progress",
            )

        # Mark as in progress
        _storage_cache["collection_status"] = "in_progress"

        try:
            items, by_instance, by_group, grand_total = await ReportsService._collect_storage(db)
            _storage_cache["items"] = items
            _storage_cache["by_gitlab_instance"] = by_instance
            _storage_cache["by_sync_group"] = by_group
            _storage_cache["grand_total"] = grand_total
            _storage_cache["collected_at"] = now
            _storage_cache["collection_status"] = "complete"
        except Exception:
            _storage_cache["collection_status"] = "error"
            raise

        return StorageReport(
            items=items,
            by_gitlab_instance=by_instance,
            by_sync_group=by_group,
            grand_total=grand_total,
            collected_at=now,
            is_stale=False,
            collection_status="complete",
        )

    @staticmethod
    async def _collect_storage(
        db: AsyncSession,
    ) -> tuple[
        list[MirrorStorageItem],
        list[StorageSummary],
        list[StorageSummary],
        StorageSummary,
    ]:
        """
        Actually query GitLab API for each mirror's target project size.
        Returns (items, by_instance, by_group, grand_total).
        """
        mirrors = await ReportsService._get_all_active_mirrors(db)

        # Pre-build GitLab clients per instance (cached per instance_id)
        instance_clients: dict[int, GitLabService] = {}
        gl_service = GitLabService()

        items: list[MirrorStorageItem] = []

        # Aggregation accumulators
        instance_agg: dict[str, dict[str, int]] = defaultdict(
            lambda: {"repo": 0, "history": 0, "total": 0}
        )
        group_agg: dict[str, dict[str, int]] = defaultdict(
            lambda: {"repo": 0, "history": 0, "total": 0}
        )
        grand_repo = 0
        grand_history = 0
        grand_total = 0

        for m in mirrors:
            sr = m.source_repository
            source_url = _source_url_from_repo(sr) if sr else "N/A"
            target_gl_name = m.target_gitlab_instance.name if m.target_gitlab_instance else "N/A"
            target_path = _derive_target_path(m.target_namespace, m.target_project_name)
            sg_name = m.sync_group.name if m.sync_group else None
            instance_key = target_gl_name
            group_key = sg_name or "No SyncGroup"

            repo_size = None
            history_size = None
            total_size = None
            error_msg = None
            accessible = False

            # Try to get project size from GitLab API
            if m.target_project_id and m.target_project_id.isdigit() and m.target_gitlab_instance:
                try:
                    instance_id = m.target_gitlab_instance.id
                    if instance_id not in instance_clients:
                        instance_clients[instance_id] = gl_service
                    client = gl_service._get_client(m.target_gitlab_instance)
                    project = client.projects.get(int(m.target_project_id), statistics=True)
                    # GitLab returns storage in MB under 'statistics' field
                    statistics = getattr(project, "statistics", None)
                    if statistics:
                        # statistics.repository_size is in bytes
                        repo_size = getattr(statistics, "repository_size", 0) or 0
                        # lfs_objects_size + build_artifacts_size + packages_size etc.
                        other_items = [
                            getattr(statistics, "lfs_objects_size", 0) or 0,
                            getattr(statistics, "build_artifacts_size", 0) or 0,
                            getattr(statistics, "packages_size", 0) or 0,
                            getattr(statistics, "wiki_size", 0) or 0,
                            getattr(statistics, "snippets_size", 0) or 0,
                        ]
                        history_size = sum(other_items)
                        total_size = repo_size + history_size
                        accessible = True
                except Exception as exc:
                    error_msg = str(exc)
                    logger.warning(
                        "Storage: could not get project %s for mirror %d: %s",
                        m.target_project_id,
                        m.id,
                        exc,
                    )

            item = MirrorStorageItem(
                mirror_id=m.id,
                source_url=source_url,
                target_gitlab_instance_name=target_gl_name,
                target_path=target_path,
                sync_group_name=sg_name,
                repo_size_bytes=repo_size,
                history_size_bytes=history_size,
                total_size_bytes=total_size,
                error=error_msg,
                accessible=accessible,
            )
            items.append(item)

            if accessible and total_size is not None:
                instance_agg[instance_key]["repo"] += repo_size or 0
                instance_agg[instance_key]["history"] += history_size or 0
                instance_agg[instance_key]["total"] += total_size
                group_agg[group_key]["repo"] += repo_size or 0
                group_agg[group_key]["history"] += history_size or 0
                group_agg[group_key]["total"] += total_size
                grand_repo += repo_size or 0
                grand_history += history_size or 0
                grand_total += total_size

        by_instance = [
            StorageSummary(
                key=k,
                repo_size_bytes=v["repo"],
                history_size_bytes=v["history"],
                total_size_bytes=v["total"],
            )
            for k, v in sorted(instance_agg.items())
        ]
        by_group = [
            StorageSummary(
                key=k,
                repo_size_bytes=v["repo"],
                history_size_bytes=v["history"],
                total_size_bytes=v["total"],
            )
            for k, v in sorted(group_agg.items())
        ]

        grand = StorageSummary(
            key="Итого",
            repo_size_bytes=grand_repo,
            history_size_bytes=grand_history,
            total_size_bytes=grand_total,
        )

        return items, by_instance, by_group, grand

    @staticmethod
    async def refresh_storage(db: AsyncSession) -> StorageReport:
        """Force-refresh the storage cache."""
        return await ReportsService.report_storage(db, force_refresh=True)

    # ........................................................................
    # 3. Status Report
    # ........................................................................

    @staticmethod
    async def report_status(db: AsyncSession, trend_days: int = 0) -> StatusReport:
        """
        Report mirrors grouped by status flag.

        If trend_days > 0, this also returns how many mirrors *changed*
        status in the given period (for now, returns current snapshot with
        trend derived from MirrorLog status changes).
        """
        mirrors = await ReportsService._get_all_active_mirrors(db)

        # Group by status
        status_buckets: dict[int, list[Mirror]] = {
            STATUS_OK: [],
            STATUS_FAILED: [],
            STATUS_WARNING: [],
            STATUS_IN_PROGRESS: [],
            STATUS_PENDING: [],
        }

        for m in mirrors:
            bucket = status_buckets.get(m.status_flag)
            if bucket is not None:
                bucket.append(m)

        status_counts = []
        for flag in [STATUS_OK, STATUS_FAILED, STATUS_WARNING, STATUS_IN_PROGRESS, STATUS_PENDING]:
            bucket = status_buckets[flag]
            status_counts.append(
                StatusCountItem(
                    status_flag=flag,
                    status_text=ReportsService._status_text(flag),
                    count=len(bucket),
                    label=ReportsService._status_text(flag),
                )
            )

        def _to_item(m: Mirror) -> MirrorStatusItem:
            sr = m.source_repository
            return MirrorStatusItem(
                mirror_id=m.id,
                source_url=_source_url_from_repo(sr) if sr else "N/A",
                status_flag=m.status_flag,
                status_text=m.status_text,
                target_path=_derive_target_path(m.target_namespace, m.target_project_name),
                sync_group_name=m.sync_group.name if m.sync_group else None,
            )

        return StatusReport(
            status_counts=status_counts,
            total_mirrors=len(mirrors),
            ok_mirrors=[_to_item(m) for m in status_buckets[STATUS_OK]],
            failed_mirrors=[_to_item(m) for m in status_buckets[STATUS_FAILED]],
            warning_mirrors=[_to_item(m) for m in status_buckets[STATUS_WARNING]],
            in_progress_mirrors=[_to_item(m) for m in status_buckets[STATUS_IN_PROGRESS]],
            pending_mirrors=[_to_item(m) for m in status_buckets[STATUS_PENDING]],
        )

    # ........................................................................
    # 4. Syncs Report
    # ........................................................................

    @staticmethod
    async def report_syncs(
        db: AsyncSession,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> SyncsReport:
        """
        Report sync activity over a date range.

        Defaults to last 30 days if no period is provided.
        """
        now_utc = datetime.now(UTC)
        if period_end is None:
            period_end = now_utc.date()
        if period_start is None:
            period_start = period_end - timedelta(days=30)

        # Fetch all sync logs in the period
        start_dt = datetime(period_start.year, period_start.month, period_start.day, tzinfo=UTC)
        end_dt = datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=UTC)

        result = await db.execute(
            select(MirrorLog)
            .options(
                selectinload(MirrorLog.mirror).selectinload(Mirror.source_repository),
                selectinload(MirrorLog.mirror).selectinload(Mirror.sync_group),
            )
            .where(
                MirrorLog.log_type == MirrorLogType.sync,
                MirrorLog.created_at >= start_dt,
                MirrorLog.created_at <= end_dt,
            )
            .order_by(MirrorLog.created_at)
        )
        logs = list(result.unique().scalars().all())

        # Daily aggregation
        daily_map: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "successful": 0, "failed": 0, "stale": 0}
        )
        # By sync group
        group_map: dict[str, dict[str, int]] = defaultdict(
            lambda: {"total": 0, "successful": 0, "failed": 0, "stale": 0}
        )
        # Per-mirror counters
        mirror_syncs: dict[int, int] = defaultdict(int)
        mirror_errors: dict[int, int] = defaultdict(int)
        # Mirror metadata (for top lists)
        mirror_meta: dict[int, tuple[str, str]] = {}  # mirror_id → (source_url, target_path)

        for log in logs:
            m = log.mirror if log.mirror else None
            if m is None:
                continue

            day_str = log.created_at.strftime("%Y-%m-%d")
            daily_map[day_str]["total"] += 1

            if log.status_flag == STATUS_OK:
                daily_map[day_str]["successful"] += 1
            elif log.status_flag == STATUS_FAILED:
                daily_map[day_str]["failed"] += 1
            elif log.status_flag == STATUS_WARNING:
                daily_map[day_str]["stale"] += 1

            sg_name = m.sync_group.name if m.sync_group else "No SyncGroup"
            group_map[sg_name]["total"] += 1
            if log.status_flag == STATUS_OK:
                group_map[sg_name]["successful"] += 1
            elif log.status_flag == STATUS_FAILED:
                group_map[sg_name]["failed"] += 1
            elif log.status_flag == STATUS_WARNING:
                group_map[sg_name]["stale"] += 1

            mirror_syncs[m.id] += 1
            if log.status_flag == STATUS_FAILED:
                mirror_errors[m.id] += 1

            if m.id not in mirror_meta:
                sr = m.source_repository
                mirror_meta[m.id] = (
                    _source_url_from_repo(sr) if sr else "N/A",
                    _derive_target_path(m.target_namespace, m.target_project_name),
                )

        # Build daily list
        daily: list[DailySyncsItem] = []
        cursor = period_start
        while cursor <= period_end:
            day_str = cursor.strftime("%Y-%m-%d")
            d = daily_map.get(day_str, {"total": 0, "successful": 0, "failed": 0, "stale": 0})
            daily.append(
                DailySyncsItem(
                    date=day_str,
                    total=d["total"],
                    successful=d["successful"],
                    failed=d["failed"],
                    stale=d["stale"],
                )
            )
            cursor += timedelta(days=1)

        # By sync group
        by_group = [
            SyncGroupSyncsItem(
                sync_group_name=k,
                total=v["total"],
                successful=v["successful"],
                failed=v["failed"],
                stale=v["stale"],
            )
            for k, v in sorted(group_map.items())
        ]

        # Top-10 by syncs
        top_syncs = sorted(mirror_syncs.items(), key=lambda x: x[1], reverse=True)[:10]
        top_by_syncs = [
            TopSyncMirrorItem(
                mirror_id=mid,
                source_url=mirror_meta[mid][0],
                taget_path=mirror_meta[mid][1],  # note: intentionally matches schema field name
                count=cnt,
            )
            for mid, cnt in top_syncs
        ]

        # Top-10 by errors
        top_errs = sorted(mirror_errors.items(), key=lambda x: x[1], reverse=True)[:10]
        top_by_errors = [
            TopSyncMirrorItem(
                mirror_id=mid,
                source_url=mirror_meta[mid][0],
                taget_path=mirror_meta[mid][1],
                count=cnt,
            )
            for mid, cnt in top_errs
        ]

        return SyncsReport(
            period_start=period_start.strftime("%Y-%m-%d"),
            period_end=period_end.strftime("%Y-%m-%d"),
            daily=daily,
            by_sync_group=by_group,
            top_by_syncs=top_by_syncs,
            top_by_errors=top_by_errors,
        )

    # ........................................................................
    # Bulk Operations
    # ........................................................................

    @staticmethod
    async def bulk_reassign_sync_group(
        db: AsyncSession,
        data: BulkReassignSyncGroupRequest,
    ) -> BulkOperationResponse:
        """Bulk reassign mirrors to a different SyncGroup."""
        return await ReportsService._bulk_operation(
            db=db,
            operation="reassign-sync-group",
            mirror_ids=data.mirror_ids,
            apply_fn=lambda m: setattr(m, "sync_group_id", data.sync_group_id),
        )

    @staticmethod
    async def bulk_change_target_gitlab(
        db: AsyncSession,
        data: BulkChangeTargetGitlabRequest,
    ) -> BulkOperationResponse:
        """
        Bulk change target GitLab provider by reassigning mirrors to a SyncGroup
        that has the desired Pipeline → ResourceProvider chain.
        """
        return await ReportsService._bulk_operation(
            db=db,
            operation="change-target-gitlab",
            mirror_ids=data.mirror_ids,
            apply_fn=lambda m: setattr(m, "sync_group_id", data.sync_group_id),
        )

    @staticmethod
    async def bulk_apply_pipeline(
        db: AsyncSession,
        data: BulkApplyPipelineRequest,
    ) -> BulkOperationResponse:
        """
        Bulk apply a Pipeline to mirrors by updating their SyncGroup's
        pipeline assignment.

        Since mirrors belonging to different SyncGroups would need different
        handling, we apply the pipeline to each mirror's sync_group.
        Mirrors with no sync_group get an error result.
        """
        results: list[BulkOperationResultItem] = []
        succeeded = 0
        failed = 0

        for mirror_id in data.mirror_ids:
            try:
                stmt = (
                    select(Mirror)
                    .options(selectinload(Mirror.sync_group))
                    .where(Mirror.id == mirror_id, ~Mirror.is_deleted)
                )
                result = await db.execute(stmt)
                mirror = result.scalar_one_or_none()

                if mirror is None:
                    results.append(
                        BulkOperationResultItem(
                            mirror_id=mirror_id,
                            success=False,
                            message=f"Mirror {mirror_id} not found or deleted",
                        )
                    )
                    failed += 1
                    continue

                if mirror.sync_group is None:
                    results.append(
                        BulkOperationResultItem(
                            mirror_id=mirror_id,
                            success=False,
                            message=f"Mirror {mirror_id} has no SyncGroup assigned",
                        )
                    )
                    failed += 1
                    continue

                mirror.sync_group.pipeline_id = data.pipeline_id
                await db.flush()
                results.append(
                    BulkOperationResultItem(
                        mirror_id=mirror_id,
                        success=True,
                        message=f"Pipeline {data.pipeline_id} applied to SyncGroup "
                        f"{mirror.sync_group.name}",
                    )
                )
                succeeded += 1
            except Exception as exc:
                results.append(
                    BulkOperationResultItem(
                        mirror_id=mirror_id,
                        success=False,
                        message=str(exc),
                    )
                )
                failed += 1

        await db.commit()
        return BulkOperationResponse(
            operation="apply-pipeline",
            total=len(data.mirror_ids),
            succeeded=succeeded,
            failed=failed,
            results=results,
        )

    @staticmethod
    async def _bulk_operation(
        db: AsyncSession,
        operation: str,
        mirror_ids: list[int],
        apply_fn: callable,
    ) -> BulkOperationResponse:
        """Generic bulk operation: fetch mirrors, apply change, collect results."""
        results: list[BulkOperationResultItem] = []
        succeeded = 0
        failed = 0

        stmt = (
            select(Mirror)
            .options(selectinload(Mirror.sync_group))
            .where(Mirror.id.in_(mirror_ids), ~Mirror.is_deleted)
        )
        result = await db.execute(stmt)
        mirrors = {m.id: m for m in result.unique().scalars().all()}

        for mirror_id in mirror_ids:
            if mirror_id not in mirrors:
                results.append(
                    BulkOperationResultItem(
                        mirror_id=mirror_id,
                        success=False,
                        message=f"Mirror {mirror_id} not found or deleted",
                    )
                )
                failed += 1
                continue

            try:
                mirror = mirrors[mirror_id]
                apply_fn(mirror)
                await db.flush()
                results.append(
                    BulkOperationResultItem(
                        mirror_id=mirror_id,
                        success=True,
                        message=None,
                    )
                )
                succeeded += 1
            except Exception as exc:
                results.append(
                    BulkOperationResultItem(
                        mirror_id=mirror_id,
                        success=False,
                        message=str(exc),
                    )
                )
                failed += 1

        await db.commit()
        return BulkOperationResponse(
            operation=operation,
            total=len(mirror_ids),
            succeeded=succeeded,
            failed=failed,
            results=results,
        )


# Module-level singleton for convenience
reports_service = ReportsService()
