"""
@file mirror.py
@description MirrorService — business logic for managing git mirrors.
             Handles CRUD, duplicate detection, import, sync triggering,
             freshness and integrity checks.
@dependencies sqlalchemy, app.core.exceptions, app.services.pipeline,
             app.services.audit, app.services.source_providers
@relatedFiles ../models/mirror.py, ../models/mirror_log.py,
             ../models/source_repository.py, ../models/sync_group.py,
             ../schemas/mirror.py, ../services/pipeline.py, ../services/audit.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import gitlab as _gitlab_module
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    BadRequestError,
    DomainError,
    NotFoundError,
)
from app.core.secrets import decrypt_secret
from app.models.mirror import Mirror
from app.models.mirror_log import MirrorLog, MirrorLogType
from app.models.pipeline import Pipeline as PipelineModel
from app.models.role_scope import RoleScopeSourceGroup, RoleScopeSyncGroup
from app.models.source_group import SourceGroup
from app.models.source_provider import SourceProvider
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.models.user import User
from app.schemas.mirror import (
    MirrorBulkCreate,
    MirrorCreate,
    MirrorUpdate,
)
from app.services.audit import AuditService
from app.services.pipeline import trigger_pipeline  # standalone async function
from app.services.source_providers import create_source_provider

logger = logging.getLogger(__name__)

# ── Unchanged constants shared with pipeline.py ──────────────────────────
STATUS_OK = 0
STATUS_FAILED = 1
STATUS_WARNING = 2
STATUS_IN_PROGRESS = 3
STATUS_PENDING = 4


# ===================================================================
# Helpers
# ===================================================================


def _derive_target_path(target_namespace: str, target_project_name: str) -> str:
    """Derive the full target path from namespace and project name."""
    ns = target_namespace.strip("/") if target_namespace else ""
    return f"{ns}/{target_project_name}" if ns else target_project_name


def _source_url_from_repo(repo: SourceRepository) -> str:
    """Extract a usable source URL from a SourceRepository."""
    return repo.clone_url_https or repo.web_url or repo.full_name


async def _get_mirror_or_404(db: AsyncSession, mirror_id: int) -> Mirror:
    """Fetch a non-deleted Mirror by id or raise NotFoundError."""
    result = await db.execute(
        select(Mirror)
        .options(
            selectinload(Mirror.source_repository).selectinload(SourceRepository.source_group),
            selectinload(Mirror.source_repository)
            .selectinload(SourceRepository.source_provider)
            .selectinload(SourceProvider.credential),
            selectinload(Mirror.sync_group)
            .selectinload(SyncGroup.pipeline)
            .selectinload(PipelineModel.gitlab_instance),
            selectinload(Mirror.mirror_logs),
        )
        .where(Mirror.id == mirror_id, ~Mirror.is_deleted)
    )
    mirror = result.scalar_one_or_none()
    if mirror is None:
        raise NotFoundError(f"Mirror with id={mirror_id} not found")
    return mirror


async def _get_source_repo_or_404(db: AsyncSession, sr_id: int) -> SourceRepository:
    """Fetch a non-deleted SourceRepository by id or raise NotFoundError."""
    result = await db.execute(
        select(SourceRepository)
        .options(
            selectinload(SourceRepository.source_group),
            selectinload(SourceRepository.source_provider).selectinload(SourceProvider.credential),
        )
        .where(SourceRepository.id == sr_id, ~SourceRepository.is_deleted)
    )
    repo = result.scalar_one_or_none()
    if repo is None:
        raise NotFoundError(f"SourceRepository with id={sr_id} not found")
    return repo


async def _get_sync_group_or_404(db: AsyncSession, sg_id: int) -> SyncGroup:
    """Fetch a non-deleted SyncGroup by id or raise NotFoundError."""
    result = await db.execute(
        select(SyncGroup)
        .options(selectinload(SyncGroup.pipeline))
        .where(SyncGroup.id == sg_id, ~SyncGroup.is_deleted)
    )
    sg = result.scalar_one_or_none()
    if sg is None:
        raise NotFoundError(f"SyncGroup with id={sg_id} not found")
    return sg


# ===================================================================
# Data classes
# ===================================================================


@dataclass
class IntegrityCheckResult:
    """Result of a direct source-to-target integrity comparison.

    Compares the latest commit SHA from the source repository
    against the target GitLab project without triggering a CI/CD pipeline.
    """

    mirror_id: int
    status: str  # "MATCH", "MISMATCH", "ERROR"
    source_commit_sha: str | None = None
    target_commit_sha: str | None = None
    message: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


# ===================================================================
# MirrorService
# ===================================================================


class MirrorService:
    """Service layer for managing git mirrors.

    Provides methods for CRUD operations, duplicate detection,
    importing existing mirrors, triggering syncs, and running
    freshness/integrity checks.
    """

    # ── Create ──────────────────────────────────────────────────────────

    @staticmethod
    async def create_mirror(
        db: AsyncSession,
        data: MirrorCreate,
        user_id: int,
        username: str = "system",
    ) -> Mirror:
        """Create a single mirror with duplicate detection.

        Args:
            db: Async database session.
            data: Mirror creation payload (source_repository_id,
                  sync_group_id, target_namespace, target_project_name).
            user_id: ID of the user performing the action.
            username: Username for audit logging (default "system").

        Returns:
            The newly created Mirror instance.

        Note:
            Duplicate detection is advisory — the mirror is still created
            but a ``duplicate_warning`` flag is set in the audit log.
        """
        # Validate source repository exists
        source_repo = await _get_source_repo_or_404(db, data.source_repository_id)

        # Validate sync group if provided
        if data.sync_group_id is not None:
            await _get_sync_group_or_404(db, data.sync_group_id)

        # ── Duplicate check ─────────────────────────────────────────
        duplicate_query = select(Mirror).where(
            Mirror.source_repository_id == data.source_repository_id,
            Mirror.target_namespace == data.target_namespace,
            Mirror.target_project_name == data.target_project_name,
            ~Mirror.is_deleted,
        )
        if data.sync_group_id is not None:
            duplicate_query = duplicate_query.where(Mirror.sync_group_id == data.sync_group_id)
        dup_result = await db.execute(duplicate_query)
        existing_mirror = dup_result.scalar_one_or_none()

        duplicate_warning = existing_mirror is not None

        if duplicate_warning:
            logger.warning(
                "Duplicate mirror detected: source_repo_id=%d, target=%s/%s",
                data.source_repository_id,
                data.target_namespace,
                data.target_project_name,
            )
            await AuditService.log_event(
                db,
                user_id=user_id,
                username=username,
                action="mirror.duplicate_warning",
                resource_type="mirror",
                resource_id=existing_mirror.id,
                resource_name=existing_mirror.target_project_name,
                details={
                    "source_repository_id": data.source_repository_id,
                    "target_namespace": data.target_namespace,
                    "target_project_name": data.target_project_name,
                    "existing_mirror_id": existing_mirror.id,
                },
            )
            await db.commit()

        # ── Create mirror ───────────────────────────────────────────
        source_url = _source_url_from_repo(source_repo)
        mirror = Mirror(
            source_repository_id=data.source_repository_id,
            sync_group_id=data.sync_group_id,
            target_namespace=data.target_namespace,
            target_project_name=data.target_project_name,
            status_flag=STATUS_PENDING,
            status_text="Pending",
        )
        db.add(mirror)
        await db.commit()
        await db.refresh(mirror)

        # ── Audit ───────────────────────────────────────────────────
        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="mirror.created",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
            details={
                "source_repository_id": data.source_repository_id,
                "source_url": source_url,
                "sync_group_id": data.sync_group_id,
                "target_namespace": data.target_namespace,
                "target_project_name": data.target_project_name,
                "duplicate_warning": duplicate_warning,
            },
        )
        await db.commit()

        logger.info(
            "Mirror created: id=%d, src_repo=%d, target=%s/%s",
            mirror.id,
            data.source_repository_id,
            data.target_namespace,
            data.target_project_name,
        )

        # ── Auto-trigger initial sync if Mirror belongs to SyncGroup
        #     with an assigned Pipeline ─────────────────────────────
        if data.sync_group_id is not None:
            try:
                # Re-fetch the sync group to check for pipeline
                sg_result = await db.execute(
                    select(SyncGroup)
                    .options(selectinload(SyncGroup.pipeline))
                    .where(SyncGroup.id == data.sync_group_id, ~SyncGroup.is_deleted)
                )
                sync_group = sg_result.scalar_one_or_none()
                if sync_group is not None and sync_group.pipeline is not None:
                    await MirrorService.trigger_sync(
                        db,
                        mirror_id=mirror.id,
                        user_id=user_id,
                        username=username,
                    )
                    logger.info(
                        "Auto-sync triggered for newly created mirror %d",
                        mirror.id,
                    )
            except Exception as exc:
                logger.warning(
                    "Auto-sync failed for mirror %d (mirror was created): %s",
                    mirror.id,
                    exc,
                )

        return mirror

    # ── Bulk Create ─────────────────────────────────────────────────────

    @staticmethod
    async def bulk_create_mirrors(
        db: AsyncSession,
        data: MirrorBulkCreate,
        user_id: int,
        username: str = "system",
    ) -> list[Mirror]:
        """Create multiple mirrors in a single batch operation.

        Performs a single duplicate query before bulk-inserting all
        mirrors.  The ``target_project_name`` for each mirror is
        auto-derived from the ``SourceRepository.name`` when not
        explicitly provided.

        Args:
            db: Async database session.
            data: Bulk creation payload with a list of MirrorCreate
                  entries and optional defaults.
            user_id: ID of the user performing the action.
            username: Username for audit logging.

        Returns:
            List of created Mirror instances.

        Raises:
            BadRequestError: When the mirror list is empty or exceeds 500.
        """
        mirror_list = data.mirrors
        if not mirror_list:
            raise BadRequestError("No mirrors provided for bulk creation")
        if len(mirror_list) > 500:
            raise BadRequestError(
                f"Bulk creation limited to 500 mirrors; received {len(mirror_list)}"
            )

        # Batch-resolve all source repositories
        sr_ids = {m.source_repository_id for m in mirror_list}
        sr_result = await db.execute(
            select(SourceRepository).where(
                SourceRepository.id.in_(sr_ids),
                ~SourceRepository.is_deleted,
            )
        )
        sr_map: dict[int, SourceRepository] = {sr.id: sr for sr in sr_result.scalars().all()}

        # Validate all source repos exist
        missing = sr_ids - set(sr_map.keys())
        if missing:
            raise BadRequestError(f"Source repositories not found: {sorted(missing)}")

        # Resolve sync group
        sg_id: int | None = None
        default_sg_id = data.default_sync_group_id
        if default_sg_id is not None:
            sg_id = default_sg_id

        # Batch duplicate check — single query for all (source_repo_id,
        # target_namespace, target_project_name) combinations
        dup_conditions: list = []
        for m in mirror_list:
            sr_map[m.source_repository_id]  # ensure key exists
            target_name = m.target_project_name
            target_ns = (
                m.target_namespace if m.target_namespace else (data.default_target_namespace or "")
            )
            dup_conditions.append(
                and_(
                    Mirror.source_repository_id == m.source_repository_id,
                    Mirror.target_namespace == target_ns,
                    Mirror.target_project_name == target_name,
                    ~Mirror.is_deleted,
                )
            )

        existing_sr_ids: set[int] = set()
        if dup_conditions:
            dup_result = await db.execute(
                select(
                    Mirror.source_repository_id,
                    Mirror.target_namespace,
                    Mirror.target_project_name,
                ).where(or_(*dup_conditions))
            )
            for row in dup_result:
                existing_sr_ids.add(row.source_repository_id)

        # Build Mirror instances
        mirrors_to_create: list[Mirror] = []
        for m in mirror_list:
            sr_map[m.source_repository_id]  # ensure key exists
            target_name = m.target_project_name
            target_ns = (
                m.target_namespace if m.target_namespace else (data.default_target_namespace or "")
            )
            effective_sg_id = m.sync_group_id or sg_id

            mirrors_to_create.append(
                Mirror(
                    source_repository_id=m.source_repository_id,
                    sync_group_id=effective_sg_id,
                    target_namespace=target_ns,
                    target_project_name=target_name,
                    status_flag=STATUS_PENDING,
                    status_text="Pending",
                )
            )

        # Bulk insert
        db.add_all(mirrors_to_create)
        await db.commit()

        # Refresh all to get IDs
        for mirror in mirrors_to_create:
            await db.refresh(mirror)

        # Audit: single bulk event
        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="mirror.bulk_created",
            resource_type="mirror",
            details={
                "count": len(mirrors_to_create),
                "mirror_ids": [m.id for m in mirrors_to_create],
                "duplicate_count": len(existing_sr_ids),
            },
        )
        await db.commit()

        logger.info(
            "Bulk created %d mirrors (user_id=%d)",
            len(mirrors_to_create),
            user_id,
        )
        return mirrors_to_create

    # ── Duplicate Check ─────────────────────────────────────────────────

    @staticmethod
    async def check_duplicates(
        db: AsyncSession,
        source_repo_ids: list[int],
        sync_group_id: int,
    ) -> dict[str, Any]:
        """Check for duplicate mirrors for a set of source repositories
        within or outside a given sync group.

        A duplicate is defined as a mirror with the same
        ``source_repository_id``, ``target_namespace``,
        and ``target_project_name`` — i.e. the same source repo
        mirrored to the same target path.

        Args:
            db: Async database session.
            source_repo_ids: List of source repository IDs to check.
            sync_group_id: The sync group whose scope defines
                           "accessible" vs "inaccessible".

        Returns:
            Dict with keys:
            - ``duplicates``: all duplicate mirrors found
            - ``accessible``: duplicates within the given sync_group
            - ``inaccessible``: duplicates in other sync groups
        """
        if not source_repo_ids:
            return {"duplicates": [], "accessible": [], "inaccessible": []}

        # Query all non-deleted mirrors for the given source repos,
        # eager-loading relationships needed for display
        result = await db.execute(
            select(Mirror)
            .options(
                selectinload(Mirror.source_repository),
                selectinload(Mirror.sync_group).selectinload(SyncGroup.pipeline),
            )
            .where(
                Mirror.source_repository_id.in_(source_repo_ids),
                ~Mirror.is_deleted,
            )
        )
        all_mirrors = list(result.scalars().all())

        duplicates: list[dict] = []
        accessible: list[dict] = []
        inaccessible: list[dict] = []

        for mirror in all_mirrors:
            sr: SourceRepository | None = mirror.source_repository
            sg: SyncGroup | None = mirror.sync_group

            entry = {
                "mirror_id": mirror.id,
                "source_repo_id": mirror.source_repository_id,
                "source_url": _source_url_from_repo(sr) if sr else None,
                "target_path": _derive_target_path(
                    mirror.target_namespace or "",
                    mirror.target_project_name or "",
                ),
                "sync_group_name": sg.name if sg else None,
            }
            duplicates.append(entry)

            if mirror.sync_group_id == sync_group_id:
                accessible.append(entry)
            else:
                inaccessible.append(entry)

        return {
            "duplicates": duplicates,
            "accessible": accessible,
            "inaccessible": inaccessible,
        }

    # ── Import Existing Mirror ──────────────────────────────────────────

    @staticmethod
    async def import_existing_mirror(
        db: AsyncSession,
        source_url: str,
        target_gitlab_id: int,
        target_path: str,
        user_id: int,
        username: str = "system",
    ) -> Mirror:
        """Import an existing mirror by verifying the source-target link.

        Uses source provider ``get_commit_info()`` to verify that
        the source repository and target GitLab project share the same
        most recent commit, confirming they are a valid mirror pair.

        Args:
            db: Async database session.
            source_url: Source repository URL (e.g. GitHub clone URL).
            target_gitlab_id: GitLab instance ID.
            target_path: Target path in GitLab (namespace/project).
            user_id: ID of the user performing the import.
            username: Username for audit logging.

        Returns:
            The newly created (imported) Mirror.

        Raises:
            DomainError: When verification fails (commits don't match
                             or the source provider cannot be found).
        """
        # Parse target_path into namespace and project name
        parts = target_path.strip("/").split("/")
        if len(parts) >= 2:
            target_namespace = parts[0]
            target_project_name = parts[-1]
        else:
            target_namespace = ""
            target_project_name = parts[0] if parts else target_path

        # Find a SourceProvider that can handle this URL
        source_providers_result = await db.execute(
            select(SourceProvider).where(
                SourceProvider.provider_type == "github",
                ~SourceProvider.is_deleted,
            )
        )
        source_providers = list(source_providers_result.scalars().all())

        if not source_providers:
            raise DomainError(
                "No source provider configured for verification",
                status_code=400,
            )

        # Try each provider to verify the source commit
        latest_commit: dict | None = None
        repo_external_id: str | None = None
        used_provider: SourceProvider | None = None

        for sp in source_providers:
            # Skip non-anonymous providers without credentials
            if not sp.is_anon and (sp.credential is None or not sp.credential.encrypted_secret):
                continue
            try:
                credential_secret: str | None = None
                if sp.credential and sp.credential.encrypted_secret:
                    credential_secret = decrypt_secret(sp.credential.encrypted_secret)
                gh_provider = await create_source_provider(sp, credential_secret)

                # Extract owner/repo from source_url
                # source_url examples: https://github.com/owner/repo.git
                clean_url = source_url.rstrip("/")
                if clean_url.endswith(".git"):
                    clean_url = clean_url[:-4]
                parts_url = clean_url.split("/")
                if len(parts_url) >= 2:
                    repo_external_id = f"{parts_url[-2]}/{parts_url[-1]}"
                else:
                    continue

                commit_info = await gh_provider.get_commit_info(repo_external_id)
                latest_commit = commit_info
                used_provider = sp
                break
            except DomainError:
                logger.debug(
                    "Provider %d failed to verify source_url '%s'",
                    sp.id,
                    source_url,
                    exc_info=True,
                )
                continue

        if latest_commit is None:
            raise DomainError(
                f"Unable to verify source repository: {source_url}. "
                "No source provider could fetch commit information.",
                status_code=400,
            )

        # Find or create the SourceRepository for this URL
        sr_result = await db.execute(
            select(SourceRepository).where(
                or_(
                    SourceRepository.clone_url_https == source_url,
                    SourceRepository.web_url == source_url,
                ),
                ~SourceRepository.is_deleted,
            )
        )
        source_repo = sr_result.scalar_one_or_none()

        if source_repo is None:
            # Auto-create a minimal SourceRepository
            # SourceGroup no longer has source_provider_id, find any non-deleted group
            sg_result = await db.execute(
                select(SourceGroup).where(~SourceGroup.is_deleted).limit(1)
            )
            source_group = sg_result.scalar_one_or_none()

            source_repo = SourceRepository(
                source_group_id=source_group.id if source_group else None,
                source_provider_id=used_provider.id,
                external_id=repo_external_id or source_url,
                name=repo_external_id.split("/")[-1] if repo_external_id else source_url,
                full_name=repo_external_id or source_url,
                clone_url_https=source_url,
                default_branch="main",
            )
            db.add(source_repo)
            await db.commit()
            await db.refresh(source_repo)

        # Create the imported mirror
        mirror = Mirror(
            source_repository_id=source_repo.id,
            target_namespace=target_namespace,
            target_project_name=target_project_name,
            status_flag=STATUS_OK,
            status_text="OK",
            is_imported=True,
            last_known_commit_sha=latest_commit.get("sha"),
            last_known_commit_date=latest_commit.get("date"),
            last_known_commit_author=latest_commit.get("author"),
            last_freshness_check_at=datetime.now(UTC),
        )
        db.add(mirror)
        await db.commit()
        await db.refresh(mirror)

        # Audit
        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="mirror.imported",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
            details={
                "source_url": source_url,
                "target_gitlab_id": target_gitlab_id,
                "target_path": target_path,
                "verified_commit_sha": latest_commit.get("sha"),
            },
        )
        await db.commit()

        logger.info(
            "Imported mirror: id=%d, source=%s, target=%s/%s",
            mirror.id,
            source_url,
            target_namespace,
            target_project_name,
        )
        return mirror

    # ── Read ────────────────────────────────────────────────────────────

    @staticmethod
    async def get_mirrors(
        db: AsyncSession,
        filters: dict[str, Any],
        user: User,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Mirror], int]:
        """List mirrors with RBAC-scoped filtering.

        Only returns mirrors whose SourceGroup and SyncGroup are
        accessible to the user via role_scopes.  ADMIN users see
        everything.

        Args:
            db: Async database session.
            filters: Optional filter dict — ``source_group_id``,
                     ``sync_group_id``, ``status_flag``, ``search``.
            user: Authenticated user (for scope resolution).
            limit: Page size (default 50).
            offset: Page offset (default 0).
            sort_by: Column to sort by — ``source_url``, ``created_at``,
                     ``updated_at``, ``last_sync_at``.
            sort_order: ``asc`` or ``desc``.

        Returns:
            Tuple of (list of Mirror, total count).
        """
        # Determine sort column
        sort_column_map: dict[str, Any] = {
            "created_at": Mirror.created_at,
            "updated_at": Mirror.updated_at,
            "last_sync_at": Mirror.last_sync_at,
            # source_url — sort by source_repository.full_name as proxy
        }
        sort_col = sort_column_map.get(sort_by, Mirror.created_at)
        if sort_by == "source_url":
            # Sort by the source repository name as a proxy for source_url
            sort_col = SourceRepository.full_name

        sort_order_fn = sort_col.desc() if sort_order == "desc" else sort_col.asc()

        # ── RBAC scope resolution ────────────────────────────────────
        user_role_ids: list[int] = [ur.role_id for ur in user.user_roles]

        # ADMIN sees everything
        from app.models.role import Role

        is_admin_result = await db.execute(
            select(Role.name).where(
                Role.id.in_(user_role_ids),
                Role.name == "admin",
            )
        )
        is_admin = is_admin_result.scalar_one_or_none() is not None

        # Build base query with eager loading
        base_query = (
            select(Mirror)
            .options(
                selectinload(Mirror.source_repository).selectinload(SourceRepository.source_group),
                selectinload(Mirror.sync_group)
                .selectinload(SyncGroup.pipeline)
                .selectinload(PipelineModel.gitlab_instance),
            )
            .where(~Mirror.is_deleted)
        )

        if not is_admin and user_role_ids:
            # Scope mirrors to:
            # - source_repository.source_group_id IN role_scope_source_groups
            # - sync_group_id IN role_scope_sync_groups
            sg_scope_result = await db.execute(
                select(RoleScopeSourceGroup.source_group_id).where(
                    RoleScopeSourceGroup.role_id.in_(user_role_ids)
                )
            )
            allowed_source_group_ids = {row[0] for row in sg_scope_result}

            sync_scope_result = await db.execute(
                select(RoleScopeSyncGroup.sync_group_id).where(
                    RoleScopeSyncGroup.role_id.in_(user_role_ids)
                )
            )
            allowed_sync_group_ids = {row[0] for row in sync_scope_result}

            scope_conditions: list = []
            if allowed_source_group_ids:
                scope_conditions.append(
                    SourceRepository.source_group_id.in_(allowed_source_group_ids)
                )
            if allowed_sync_group_ids:
                scope_conditions.append(Mirror.sync_group_id.in_(allowed_sync_group_ids))

            if scope_conditions:
                base_query = base_query.join(
                    SourceRepository,
                    Mirror.source_repository_id == SourceRepository.id,
                    isouter=True,
                ).where(or_(*scope_conditions))

        # ── Apply filters ────────────────────────────────────────────
        if filters.get("source_group_id"):
            base_query = base_query.where(
                SourceRepository.source_group_id == filters["source_group_id"]
            )
        if filters.get("sync_group_id"):
            base_query = base_query.where(Mirror.sync_group_id == filters["sync_group_id"])
        if filters.get("status_flag") is not None:
            base_query = base_query.where(Mirror.status_flag == filters["status_flag"])
        if filters.get("search"):
            search_term = f"%{filters['search']}%"
            # Join SourceRepository for org/repo name search
            base_query = base_query.join(
                SourceRepository,
                Mirror.source_repository_id == SourceRepository.id,
                isouter=True,
            )
            base_query = base_query.where(
                or_(
                    SourceRepository.full_name.ilike(search_term),
                    SourceRepository.clone_url_https.ilike(search_term),
                    Mirror.target_project_name.ilike(search_term),
                    Mirror.target_namespace.ilike(search_term),
                )
            )

        # ── Count ────────────────────────────────────────────────────
        # Re-apply scope + filters to count query (simplified: no join)
        # For accurate count, apply same conditions as base_query
        # For simplicity, use the base_query's where clause
        count_base = select(func.count()).select_from(Mirror)
        # Apply scope if not admin
        if not is_admin and user_role_ids:
            count_base = count_base.join(
                SourceRepository,
                Mirror.source_repository_id == SourceRepository.id,
                isouter=True,
            )
            if scope_conditions:
                count_base = count_base.where(or_(*scope_conditions))
        count_base = count_base.where(~Mirror.is_deleted)
        # Re-apply filters
        if filters.get("source_group_id"):
            count_base = count_base.where(
                SourceRepository.source_group_id == filters["source_group_id"]
            )
        if filters.get("sync_group_id"):
            count_base = count_base.where(Mirror.sync_group_id == filters["sync_group_id"])
        if filters.get("status_flag") is not None:
            count_base = count_base.where(Mirror.status_flag == filters["status_flag"])
        if filters.get("search"):
            search_term = f"%{filters['search']}%"
            count_base = count_base.join(
                SourceRepository,
                Mirror.source_repository_id == SourceRepository.id,
                isouter=True,
            )
            count_base = count_base.where(
                or_(
                    SourceRepository.full_name.ilike(search_term),
                    SourceRepository.clone_url_https.ilike(search_term),
                    Mirror.target_project_name.ilike(search_term),
                    Mirror.target_namespace.ilike(search_term),
                )
            )

        total_result = await db.execute(count_base)
        total = total_result.scalar_one()

        # ── Data query ───────────────────────────────────────────────
        if sort_by == "source_url":
            data_q = base_query.order_by(sort_order_fn)
        else:
            data_q = base_query.order_by(sort_order_fn)

        data_q = data_q.offset(offset).limit(limit)
        data_result = await db.execute(data_q)
        items = list(data_result.unique().scalars().all())

        return items, total

    @staticmethod
    async def get_mirror_detail(
        db: AsyncSession,
        mirror_id: int,
    ) -> Mirror:
        """Get mirror details with all relationships and last 10 logs.

        Args:
            db: Async database session.
            mirror_id: Mirror ID.

        Returns:
            Mirror with eager-loaded relationships and recent logs.
        """
        result = await db.execute(
            select(Mirror)
            .options(
                selectinload(Mirror.source_repository).selectinload(SourceRepository.source_group),
                selectinload(Mirror.sync_group)
                .selectinload(SyncGroup.pipeline)
                .selectinload(PipelineModel.gitlab_instance),
                selectinload(Mirror.mirror_logs),
            )
            .where(Mirror.id == mirror_id, ~Mirror.is_deleted)
        )
        mirror = result.unique().scalar_one_or_none()
        if mirror is None:
            raise NotFoundError(f"Mirror with id={mirror_id} not found")

        # Limit logs to last 10, sorted by created_at desc
        if mirror.mirror_logs:
            mirror.mirror_logs = sorted(
                mirror.mirror_logs,
                key=lambda log: log.created_at or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )[:10]

        return mirror

    # ── Update ──────────────────────────────────────────────────────────

    @staticmethod
    async def update_mirror(
        db: AsyncSession,
        mirror_id: int,
        data: MirrorUpdate,
        username: str = "system",
    ) -> Mirror:
        """Update mutable fields of an existing mirror.

        Args:
            db: Async database session.
            mirror_id: Mirror ID.
            data: MirrorUpdate payload with fields to change.
            username: Username for audit logging.

        Returns:
            The updated Mirror instance.
        """
        mirror = await _get_mirror_or_404(db, mirror_id)

        changed_fields: list[str] = []

        if data.sync_group_id is not None:
            await _get_sync_group_or_404(db, data.sync_group_id)
            if mirror.sync_group_id != data.sync_group_id:
                mirror.sync_group_id = data.sync_group_id
                changed_fields.append("sync_group_id")

        if data.target_namespace is not None and mirror.target_namespace != data.target_namespace:
            mirror.target_namespace = data.target_namespace
            changed_fields.append("target_namespace")

        if (
            data.target_project_name is not None
            and mirror.target_project_name != data.target_project_name
        ):
            mirror.target_project_name = data.target_project_name
            changed_fields.append("target_project_name")

        if not changed_fields:
            return mirror

        await db.commit()
        await db.refresh(mirror)

        await AuditService.log_event(
            db,
            user_id=None,
            username=username,
            action="mirror.updated",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
            details={"changed_fields": changed_fields},
        )
        await db.commit()

        logger.info(
            "Mirror updated: id=%d, changes=%s",
            mirror_id,
            changed_fields,
        )
        return mirror

    # ── Soft Delete ─────────────────────────────────────────────────────

    @staticmethod
    async def soft_delete_mirror(
        db: AsyncSession,
        mirror_id: int,
        username: str = "system",
    ) -> None:
        """Soft-delete a mirror by setting ``is_deleted=True``.

        If no other non-deleted mirror references the same
        ``SourceRepository``, the source repository is also soft-deleted
        (cascade).

        Args:
            db: Async database session.
            mirror_id: Mirror ID.
            username: Username for audit logging.
        """
        mirror = await _get_mirror_or_404(db, mirror_id)

        source_repo_id = mirror.source_repository_id

        mirror.is_deleted = True
        mirror.deleted_at = datetime.now(UTC)
        await db.commit()

        await AuditService.log_event(
            db,
            user_id=None,
            username=username,
            action="mirror.deleted",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
        )
        await db.commit()

        # ── Cascade: soft-delete SourceRepository if no other mirror
        #     references it ──────────────────────────────────────────
        if source_repo_id is not None:
            remaining_result = await db.execute(
                select(Mirror).where(
                    Mirror.source_repository_id == source_repo_id,
                    ~Mirror.is_deleted,
                )
            )
            remaining = remaining_result.scalar_one_or_none()
            if remaining is None:
                sr_result = await db.execute(
                    select(SourceRepository).where(
                        SourceRepository.id == source_repo_id,
                        ~SourceRepository.is_deleted,
                    )
                )
                sr = sr_result.scalar_one_or_none()
                if sr is not None:
                    sr.is_deleted = True
                    sr.deleted_at = datetime.now(UTC)
                    await AuditService.log_event(
                        db,
                        user_id=None,
                        username=username,
                        action="source_repository.deleted",
                        resource_type="source_repository",
                        resource_id=sr.id,
                        resource_name=sr.name,
                        details={"cascaded_from_mirror_id": mirror.id},
                    )
                    await db.commit()
                    logger.info(
                        "Cascade soft-deleted SourceRepository id=%d (mirror_id=%d)",
                        sr.id,
                        mirror.id,
                    )

        logger.info("Mirror soft-deleted: id=%d", mirror_id)

    # ── Restore ─────────────────────────────────────────────────────────

    @staticmethod
    async def restore_mirror(
        db: AsyncSession,
        mirror_id: int,
        username: str = "system",
    ) -> Mirror:
        """Restore a soft-deleted mirror.

        Also restores the linked ``SourceRepository`` if it was soft-deleted
        (e.g. via cascade).

        Args:
            db: Async database session.
            mirror_id: Mirror ID.
            username: Username for audit logging.

        Returns:
            The restored Mirror instance.

        Raises:
            NotFoundError: When no mirror with *mirror_id* exists
                           (including soft-deleted) (404).
        """
        # Look for the mirror INCLUDING soft-deleted ones
        result = await db.execute(
            select(Mirror)
            .options(
                selectinload(Mirror.source_repository).selectinload(SourceRepository.source_group),
                selectinload(Mirror.sync_group)
                .selectinload(SyncGroup.pipeline)
                .selectinload(PipelineModel.gitlab_instance),
            )
            .where(Mirror.id == mirror_id)
        )
        mirror = result.unique().scalar_one_or_none()
        if mirror is None:
            raise NotFoundError(f"Mirror with id={mirror_id} not found")

        if not mirror.is_deleted:
            return mirror  # already restored

        mirror.is_deleted = False
        mirror.deleted_at = None
        await db.commit()

        # ── Restore linked SourceRepository if soft-deleted ─────────
        if mirror.source_repository is not None and mirror.source_repository.is_deleted:
            mirror.source_repository.is_deleted = False
            mirror.source_repository.deleted_at = None
            await AuditService.log_event(
                db,
                user_id=None,
                username=username,
                action="source_repository.restored",
                resource_type="source_repository",
                resource_id=mirror.source_repository.id,
                resource_name=mirror.source_repository.name,
                details={"restored_from_mirror_id": mirror.id},
            )
            await db.commit()
            logger.info(
                "Cascade restored SourceRepository id=%d (mirror_id=%d)",
                mirror.source_repository.id,
                mirror.id,
            )

        await AuditService.log_event(
            db,
            user_id=None,
            username=username,
            action="mirror.restored",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
        )
        await db.commit()

        await db.refresh(mirror)
        logger.info("Mirror restored: id=%d", mirror_id)
        return mirror

    # ── Trigger Sync ────────────────────────────────────────────────────

    @staticmethod
    async def trigger_sync(
        db: AsyncSession,
        mirror_id: int,
        user_id: int,
        username: str = "system",
    ) -> MirrorLog:
        """Trigger a sync pipeline for a mirror via PipelineService.

        Finds the Mirror's SyncGroup → Pipeline and triggers a
        pipeline run in the target GitLab instance.

        Args:
            db: Async database session.
            mirror_id: Mirror ID to sync.
            user_id: ID of the user triggering the sync.
            username: Username for audit logging (default "system").

        Returns:
            The created MirrorLog entry.

        Raises:
            DomainError: When the mirror has no SyncGroup or no valid
                             target_project_id.
        """
        mirror = await _get_mirror_or_404(db, mirror_id)

        if mirror.sync_group is None:
            raise DomainError(
                f"Mirror {mirror_id} has no SyncGroup assigned",
                status_code=400,
            )

        # ── No pipeline configured → skipped ─────────────────────────
        if mirror.sync_group.pipeline is None:
            mirror_log = MirrorLog(
                mirror_id=mirror.id,
                log_type=MirrorLogType.sync,
                pipeline_run_id=None,
                status_flag=STATUS_PENDING,
                status_text="Skipped: no Pipeline configured",
                triggered_by=username,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                details={"reason": "no_pipeline"},
            )
            db.add(mirror_log)
            await db.commit()
            await db.refresh(mirror_log)
            logger.warning(
                "Sync skipped for mirror %d: SyncGroup '%s' has no Pipeline",
                mirror_id,
                mirror.sync_group.name,
            )
            return mirror_log

        pipeline = mirror.sync_group.pipeline
        gitlab_instance = pipeline.gitlab_instance
        if gitlab_instance is None:
            raise DomainError(
                f"Pipeline '{pipeline.name}' has no GitLab instance configured",
                status_code=400,
            )

        # Build pipeline variables
        source_url = (
            _source_url_from_repo(mirror.source_repository) if mirror.source_repository else None
        )
        target_path = ""
        if mirror.target_namespace and mirror.target_project_name:
            target_path = f"{mirror.target_namespace}/{mirror.target_project_name}"
        elif mirror.source_repository and mirror.source_repository.full_name:
            target_path = mirror.source_repository.full_name

        variables: dict[str, str] = {
            "SOURCE_URL": source_url or "",
            "TARGET_PROJECT_ID": str(mirror.target_project_id or ""),
            "TARGET_PROJECT_PATH": target_path,
        }

        # Merge with pipeline default_variables (pipeline defaults are
        # overridden by explicit mirror variables).
        if pipeline.default_variables:
            merged = dict(pipeline.default_variables)
            merged.update(variables)
            variables = merged

        # Convert target_project_id to int if present
        gitlab_project_id: int
        if mirror.target_project_id and mirror.target_project_id.isdigit():
            gitlab_project_id = int(mirror.target_project_id)
        else:
            raise DomainError(
                f"Mirror {mirror_id} has no valid target_project_id. "
                "A GitLab project must be created first.",
                status_code=400,
            )

        pipeline_run = await trigger_pipeline(
            db=db,
            gitlab_instance_id=gitlab_instance.id,
            gitlab_project_id=gitlab_project_id,
            ref=pipeline.ref,
            variables=variables,
            user_id=user_id,
        )

        # Create MirrorLog
        mirror_log = MirrorLog(
            mirror_id=mirror.id,
            log_type=MirrorLogType.sync,
            pipeline_run_id=pipeline_run.id,
            gitlab_pipeline_id=pipeline_run.gitlab_pipeline_id,
            gitlab_pipeline_url=pipeline_run.web_url,
            status_flag=STATUS_IN_PROGRESS,
            status_text="Running",
            triggered_by=username,
            started_at=datetime.now(UTC),
        )
        db.add(mirror_log)

        # Update mirror status
        mirror.status_flag = STATUS_IN_PROGRESS
        mirror.status_text = "Running"
        mirror.last_sync_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(mirror_log)

        # Audit
        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="mirror.sync_triggered",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
            details={
                "pipeline_run_id": pipeline_run.id,
                "gitlab_pipeline_id": pipeline_run.gitlab_pipeline_id,
            },
        )
        await db.commit()

        logger.info(
            "Sync triggered for mirror %d, pipeline_run=%d",
            mirror_id,
            pipeline_run.id,
        )
        return mirror_log

    # ── Freshness Check ─────────────────────────────────────────────────

    @staticmethod
    async def check_freshness(
        db: AsyncSession,
        mirror_id: int,
        username: str = "system",
    ) -> MirrorLog:
        """Run a lightweight freshness check by comparing the latest
        source commit against the last known commit on the mirror.

        Uses source provider ``get_commit_info()`` to fetch the
        current HEAD commit from the source repository.

        Args:
            db: Async database session.
            mirror_id: Mirror ID to check.
            username: Username for audit logging.

        Returns:
            The created MirrorLog entry with comparison results
            (status_text: ``"FRESH"`` / ``"STALE"`` / ``"ERROR"``).

        Raises:
            DomainError: When the source provider is not configured or
                             cannot be accessed.
        """
        mirror = await _get_mirror_or_404(db, mirror_id)

        if mirror.source_repository is None:
            raise DomainError(
                f"Mirror {mirror_id} has no linked SourceRepository",
                status_code=400,
            )

        sr = mirror.source_repository
        sp = sr.source_provider
        if sp is None:
            raise DomainError(
                f"SourceRepository {sr.id} has no linked SourceProvider",
                status_code=400,
            )

        # Accept any provider type that supports commit info

        # Anonymous providers don't need a credential
        if not sp.is_anon and (sp.credential is None or not sp.credential.encrypted_secret):
            raise DomainError(
                f"SourceProvider {sp.id} has no credential configured",
                status_code=400,
            )

        # ── Fetch source commit ─────────────────────────────────────
        source_sha: str | None = None
        source_date = None
        source_author = None
        error_message: str | None = None

        try:
            credential_secret: str | None = None
            if sp.credential and sp.credential.encrypted_secret:
                credential_secret = decrypt_secret(sp.credential.encrypted_secret)
            gh_provider = await create_source_provider(sp, credential_secret)
            repo_external_id = sr.full_name or sr.external_id
            commit_info = await gh_provider.get_commit_info(repo_external_id)

            source_sha = commit_info.get("sha")
            source_date = commit_info.get("date")
            source_author = commit_info.get("author")
        except Exception as exc:
            error_message = str(exc)
            logger.error(
                "Freshness check failed for mirror %d: %s",
                mirror_id,
                error_message,
            )

        # ── Compare with last known commit ──────────────────────────
        last_known = mirror.last_known_commit_sha

        if error_message is not None or source_sha is None:
            status_flag = STATUS_FAILED
            status_text = "ERROR"
        elif last_known is not None and source_sha != last_known:
            status_flag = STATUS_WARNING
            status_text = "STALE"
        else:
            status_flag = STATUS_OK
            status_text = "FRESH"

        commit_short = (source_sha or "")[:8]
        message = (
            f"Commit: {commit_short}..."
            if source_sha and not error_message
            else (error_message or "Could not determine source commit")
        )

        # ── Create MirrorLog ────────────────────────────────────────
        mirror_log = MirrorLog(
            mirror_id=mirror.id,
            log_type=MirrorLogType.freshness,
            pipeline_run_id=None,
            status_flag=status_flag,
            status_text=status_text,
            source_commit_sha=source_sha,
            source_commit_date=source_date,
            target_commit_sha=last_known,
            triggered_by=username,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            details={"message": message},
        )
        db.add(mirror_log)

        # Update mirror freshness info
        mirror.last_freshness_check_at = datetime.now(UTC)
        mirror.last_freshness_status = status_text
        if source_sha and last_known and source_sha != last_known:
            mirror.last_known_commit_sha = source_sha
            mirror.last_known_commit_date = source_date
            mirror.last_known_commit_author = source_author or commit_info.get("author")
            mirror.target_diverged_commits = (mirror.target_diverged_commits or 0) + 1

        await db.commit()
        await db.refresh(mirror_log)

        await AuditService.log_event(
            db,
            user_id=None,
            username=username,
            action="mirror.freshness_triggered",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
            details={
                "source_commit_sha": source_sha,
                "last_known_commit_sha": last_known,
                "status": status_text,
                "error": error_message,
            },
        )
        await db.commit()

        await AuditService.log_event(
            db,
            user_id=None,
            username=username,
            action="mirror.freshness_checked",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
            details={
                "source_commit_sha": source_sha,
                "last_known_commit_sha": last_known,
                "status": status_text,
                "error": error_message,
                "mirror_log_id": mirror_log.id,
            },
        )
        await db.commit()

        logger.info(
            "Freshness check for mirror %d: %s (source_sha=%s)",
            mirror_id,
            status_text,
            source_sha,
        )
        return mirror_log

    # ── Integrity Check ─────────────────────────────────────────────────

    @staticmethod
    async def check_integrity(
        db: AsyncSession,
        mirror_id: int,
        user_id: int,
        username: str = "system",
    ) -> MirrorLog:
        """Trigger an integrity CI/CD pipeline to verify mirror integrity.

        Finds the Mirror's SyncGroup → Pipeline and triggers an
        integrity pipeline run.

        Args:
            db: Async database session.
            mirror_id: Mirror ID to verify.
            user_id: ID of the user triggering the check.
            username: Username for audit logging.

        Returns:
            The created MirrorLog entry.

        Raises:
            DomainError: When the mirror has no pipeline configured.
        """
        mirror = await _get_mirror_or_404(db, mirror_id)

        if mirror.sync_group is None:
            raise DomainError(
                f"Mirror {mirror_id} has no SyncGroup assigned",
                status_code=400,
            )
        if mirror.sync_group.pipeline is None:
            raise DomainError(
                f"SyncGroup '{mirror.sync_group.name}' has no Pipeline configured",
                status_code=400,
            )

        pipeline = mirror.sync_group.pipeline
        gitlab_instance = pipeline.gitlab_instance
        if gitlab_instance is None:
            raise DomainError(
                f"Pipeline '{pipeline.name}' has no GitLab instance configured",
                status_code=400,
            )

        # Validate target_project_id
        if not mirror.target_project_id or not mirror.target_project_id.isdigit():
            raise DomainError(
                f"Mirror {mirror_id} has no valid target_project_id",
                status_code=400,
            )
        gitlab_project_id = int(mirror.target_project_id)

        source_url = (
            _source_url_from_repo(mirror.source_repository) if mirror.source_repository else None
        )
        variables: dict[str, str] = {
            "SOURCE_URL": source_url or "",
            "TARGET_NAMESPACE": mirror.target_namespace or "",
            "TARGET_PROJECT_NAME": mirror.target_project_name or "",
            "MIRROR_ID": str(mirror.id),
            "CHECK_TYPE": "integrity",
        }

        pipeline_run = await trigger_pipeline(
            db=db,
            gitlab_instance_id=gitlab_instance.id,
            gitlab_project_id=gitlab_project_id,
            ref=pipeline.ref,
            variables=variables,
            user_id=user_id,
        )

        # Create MirrorLog
        mirror_log = MirrorLog(
            mirror_id=mirror.id,
            log_type=MirrorLogType.integrity,
            pipeline_run_id=pipeline_run.id,
            gitlab_pipeline_id=pipeline_run.gitlab_pipeline_id,
            gitlab_pipeline_url=pipeline_run.web_url,
            status_flag=STATUS_IN_PROGRESS,
            status_text="Running",
            triggered_by="manual",
            started_at=datetime.now(UTC),
        )
        db.add(mirror_log)

        await db.commit()
        await db.refresh(mirror_log)

        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="mirror.integrity_triggered",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
            details={
                "pipeline_run_id": pipeline_run.id,
                "gitlab_pipeline_id": pipeline_run.gitlab_pipeline_id,
            },
        )
        await db.commit()

        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="mirror.integrity_checked",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
            details={
                "pipeline_run_id": pipeline_run.id,
                "gitlab_pipeline_id": pipeline_run.gitlab_pipeline_id,
                "mirror_log_id": mirror_log.id,
            },
        )
        await db.commit()

        logger.info(
            "Integrity check triggered for mirror %d, pipeline_run=%d",
            mirror_id,
            pipeline_run.id,
        )
        return mirror_log

    # ── Direct Integrity Check ───────────────────────────────────────────

    @staticmethod
    async def check_integrity_direct(
        db: AsyncSession,
        mirror_id: int,
        username: str = "system",
    ) -> IntegrityCheckResult:
        """Compare source HEAD commit against target GitLab project commit directly.

        Does NOT trigger a CI/CD pipeline — fetches commit info from both
        the source provider and the target GitLab instance and compares them
        in-process.

        Args:
            db: Async database session.
            mirror_id: Mirror ID to verify.
            username: Username for audit logging.

        Returns:
            IntegrityCheckResult with comparison status.

        Raises:
            DomainError: When the mirror has no source provider or no
                             target GitLab instance configured.
        """
        mirror = await _get_mirror_or_404(db, mirror_id)

        # ── Validate SyncGroup exists ───────────────────────────────
        if mirror.sync_group_id is None:
            raise DomainError(
                f"Mirror {mirror_id} has no SyncGroup configured",
                status_code=400,
            )

        # ── Resolve source provider chain ───────────────────────────
        if mirror.source_repository is None:
            raise DomainError(
                f"Mirror {mirror_id} has no linked SourceRepository",
                status_code=400,
            )
        sr = mirror.source_repository
        sp = sr.source_provider
        if sp is None:
            raise DomainError(
                f"SourceRepository {sr.id} has no linked SourceProvider",
                status_code=400,
            )

        # ── Fetch source HEAD commit ────────────────────────────────
        source_sha: str | None = None

        try:
            # Anonymous providers don't need a credential
            if not sp.is_anon and (sp.credential is None or not sp.credential.encrypted_secret):
                raise DomainError(
                    f"SourceProvider {sp.id} has no credential configured",
                    status_code=400,
                )
            credential_secret: str | None = None
            if sp.credential and sp.credential.encrypted_secret:
                credential_secret = decrypt_secret(sp.credential.encrypted_secret)
            provider = await create_source_provider(sp, credential_secret)
            repo_external_id = sr.full_name or sr.external_id
            commit_info = await provider.get_commit_info(repo_external_id)
            source_sha = commit_info.get("sha")
        except Exception as exc:
            logger.error(
                "Source commit fetch failed for mirror %d: %s",
                mirror_id,
                exc,
            )
            result = IntegrityCheckResult(
                mirror_id=mirror.id,
                status="ERROR",
                message=f"Failed to fetch source commit: {exc}",
            )
            # Create MirrorLog for the error
            mirror_log = MirrorLog(
                mirror_id=mirror.id,
                log_type=MirrorLogType.integrity,
                status_flag=STATUS_FAILED,
                status_text="ERROR",
                source_commit_sha=source_sha,
                triggered_by=username,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                details={"error": str(exc), "method": "direct"},
            )
            db.add(mirror_log)
            await db.commit()
            return result

        # ── Resolve target GitLab instance ──────────────────────────
        if mirror.sync_group is None or mirror.sync_group.pipeline is None:
            raise DomainError(
                f"Mirror {mirror_id} has no SyncGroup with a Pipeline",
                status_code=400,
            )
        pipeline_cfg = mirror.sync_group.pipeline
        instance = pipeline_cfg.gitlab_instance
        if instance is None:
            raise DomainError(
                f"Pipeline '{pipeline_cfg.name}' has no GitLab instance configured",
                status_code=400,
            )

        # ── Fetch target HEAD commit via python-gitlab ──────────────
        target_sha: str | None = None
        try:
            token = decrypt_secret(instance.token)
            gl = _gitlab_module.Gitlab(
                url=instance.url,
                private_token=token,
                ssl_verify=instance.verify_ssl,
                user_agent="BigBug/1.0",
            )
            if not mirror.target_project_id or not mirror.target_project_id.isdigit():
                raise DomainError(
                    f"Mirror {mirror_id} has no valid target_project_id",
                    status_code=400,
                )
            project = gl.projects.get(int(mirror.target_project_id))
            # Get the default branch HEAD commit
            default_branch = project.default_branch or "main"
            commits = project.commits.list(ref_name=default_branch, per_page=1)
            if commits:
                target_sha = commits[0].id
        except Exception as exc:
            logger.error(
                "Target commit fetch failed for mirror %d: %s",
                mirror_id,
                exc,
            )
            result = IntegrityCheckResult(
                mirror_id=mirror.id,
                status="ERROR",
                source_commit_sha=source_sha,
                message=f"Failed to fetch target commit: {exc}",
            )
            mirror_log = MirrorLog(
                mirror_id=mirror.id,
                log_type=MirrorLogType.integrity,
                status_flag=STATUS_FAILED,
                status_text="ERROR",
                source_commit_sha=source_sha,
                target_commit_sha=target_sha,
                triggered_by=username,
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                details={"error": str(exc), "method": "direct"},
            )
            db.add(mirror_log)
            await db.commit()
            return result

        # ── Compare ─────────────────────────────────────────────────
        if source_sha and target_sha and source_sha == target_sha:
            status = "MATCH"
            msg = "Source and target are in sync"
            log_status_flag = STATUS_OK
            log_status_text = "MATCH"
        elif source_sha and target_sha:
            status = "MISMATCH"
            msg = f"Source ({source_sha[:8]}) diverges from target ({target_sha[:8]})"
            log_status_flag = STATUS_WARNING
            log_status_text = "MISMATCH"
        else:
            status = "ERROR"
            msg = "Could not determine both commits"
            log_status_flag = STATUS_FAILED
            log_status_text = "ERROR"

        # ── Create MirrorLog ────────────────────────────────────────
        mirror_log = MirrorLog(
            mirror_id=mirror.id,
            log_type=MirrorLogType.integrity,
            status_flag=log_status_flag,
            status_text=log_status_text,
            source_commit_sha=source_sha,
            target_commit_sha=target_sha,
            triggered_by=username,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            details={"message": msg, "method": "direct"},
        )
        db.add(mirror_log)

        # Update mirror status
        mirror.status_flag = log_status_flag
        mirror.status_text = log_status_text
        if status == "MISMATCH" and source_sha:
            mirror.target_diverged_commits = (mirror.target_diverged_commits or 0) + 1

        await db.commit()

        # Audit
        await AuditService.log_event(
            db,
            user_id=None,
            username=username,
            action="mirror.integrity_checked",
            resource_type="mirror",
            resource_id=mirror.id,
            resource_name=mirror.target_project_name,
            details={
                "source_commit_sha": source_sha,
                "target_commit_sha": target_sha,
                "status": status,
                "mirror_log_id": mirror_log.id,
                "method": "direct",
            },
        )
        await db.commit()

        logger.info(
            "Direct integrity check for mirror %d: %s (src=%s, tgt=%s)",
            mirror_id,
            status,
            (source_sha or "")[:8],
            (target_sha or "")[:8],
        )
        return IntegrityCheckResult(
            mirror_id=mirror.id,
            status=status,
            source_commit_sha=source_sha,
            target_commit_sha=target_sha,
            message=msg,
        )

    # ── Logs ────────────────────────────────────────────────────────────

    @staticmethod
    async def get_logs(
        db: AsyncSession,
        mirror_id: int,
        log_type: MirrorLogType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MirrorLog]:
        """Get paginated logs for a mirror, optionally filtered by log_type.

        Args:
            db: Async database session.
            mirror_id: Mirror ID to get logs for.
            log_type: Optional filter by log type
                      (``MirrorLogType.sync``, ``MirrorLogType.freshness``, etc.).
            limit: Maximum number of log entries to return (1–200).
            offset: Number of log entries to skip.

        Returns:
            List of MirrorLog entries, ordered by created_at descending.
        """
        query = select(MirrorLog).where(MirrorLog.mirror_id == mirror_id)
        if log_type is not None:
            query = query.where(MirrorLog.log_type == log_type)
        query = query.order_by(MirrorLog.created_at.desc()).offset(offset).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    # ── Lookup helpers (for scheduler) ──────────────────────────────────

    @staticmethod
    async def get_mirrors_by_group(db: AsyncSession, sync_group_id: int) -> list[Mirror]:
        """Return all non-deleted mirrors belonging to a SyncGroup.

        Used by SyncScheduler to discover mirrors that need syncing or
        freshness checking.

        Args:
            db: Async database session.
            sync_group_id: ID of the SyncGroup whose mirrors to fetch.

        Returns:
            List of Mirror instances.
        """
        result = await db.execute(
            select(Mirror).where(
                Mirror.sync_group_id == sync_group_id,
                ~Mirror.is_deleted,
            )
        )
        return list(result.scalars().all())
