"""
@file sync_group.py
@description SyncGroupService — business logic for managing sync groups.
             Groups are logical containers that link mirrors to a shared
             pipeline, sync schedule, and freshness-checking config.
@dependencies sqlalchemy, app.core.exceptions, app.services.pipeline,
             app.services.audit
@relatedFiles ../models/sync_group.py, ../models/mirror.py,
             ../models/pipeline.py, ../schemas/sync_group.py,
             ../services/pipeline.py, ../services/audit.py
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DomainException
from app.models.mirror import Mirror
from app.models.role import Role
from app.models.role_scope import RoleScopeSyncGroup
from app.models.sync_group import SyncGroup
from app.models.user import User
from app.schemas.pipeline import PipelineCreate
from app.schemas.sync_group import SyncGroupCreate, SyncGroupUpdate
from app.services.audit import AuditService
from app.services.pipeline import (
    create_pipeline,
    get_default_pipeline,
    get_pipeline_config,
)

logger = logging.getLogger(__name__)


# ===================================================================
# SyncGroupService
# ===================================================================


class SyncGroupService:
    """Service layer for managing sync groups.

    Provides methods for CRUD operations, default group resolution,
    mass mirror assignment, and RBAC-scoped listing.
    """

    # ── Default Group ──────────────────────────────────────────────────

    @staticmethod
    async def get_default_group(db: AsyncSession) -> SyncGroup:
        """Return the default SyncGroup, creating it (and a default
        Pipeline) automatically if neither exists yet.

        The default group is the fallback bucket for all mirrors that
        are not explicitly assigned to a named group.  Its pipeline is
        used for sync operations unless overridden.

        Returns:
            SyncGroup with ``pipeline`` eagerly loaded.
        """
        result = await db.execute(
            select(SyncGroup)
            .options(selectinload(SyncGroup.pipeline))
            .where(SyncGroup.is_default, ~SyncGroup.is_deleted)
        )
        default_group = result.scalar_one_or_none()

        if default_group is not None:
            return default_group

        # ── No default SyncGroup → create one ──────────────────────────
        logger.info("No default SyncGroup found; auto-creating.")

        # Ensure a default Pipeline exists
        default_pipeline = await get_default_pipeline(db)
        if default_pipeline is None:
            logger.info("No default Pipeline found; auto-creating.")
            pipeline_create = PipelineCreate(
                name="default",
                description="Auto-created default pipeline",
                is_default=True,
            )
            default_pipeline = await create_pipeline(db, pipeline_create)
            logger.info("Created default Pipeline (id=%d)", default_pipeline.id)

        # Create default SyncGroup
        default_group = SyncGroup(
            name="default",
            description="Default sync group (auto-created)",
            pipeline_id=default_pipeline.id,
            is_default=True,
        )
        db.add(default_group)
        await db.commit()
        await db.refresh(default_group)

        # Re-fetch with eager-loaded pipeline
        result = await db.execute(
            select(SyncGroup)
            .options(selectinload(SyncGroup.pipeline))
            .where(SyncGroup.id == default_group.id)
        )
        default_group = result.scalar_one()

        logger.info(
            "Created default SyncGroup (id=%d) with pipeline_id=%d",
            default_group.id,
            default_pipeline.id,
        )
        return default_group

    # ── Create ─────────────────────────────────────────────────────────

    @staticmethod
    async def create_sync_group(
        db: AsyncSession,
        data: SyncGroupCreate,
        user_id: int,
        username: str = "system",
    ) -> SyncGroup:
        """Create a new sync group.

        Args:
            db: Async database session.
            data: SyncGroup creation payload.
            user_id: ID of the user performing the action.
            username: Username for audit logging (default ``"system"``).

        Returns:
            The newly created SyncGroup.

        Raises:
            DomainException: When *name* is already in use (409).
        """
        # ── Uniqueness check ───────────────────────────────────────────
        result = await db.execute(
            select(SyncGroup).where(
                SyncGroup.name == data.name,
                ~SyncGroup.is_deleted,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise DomainException(
                f"SyncGroup with name '{data.name}' already exists",
                status_code=409,
            )

        # ── Validate pipeline if provided ──────────────────────────────
        if data.pipeline_id is not None:
            pipeline = await get_pipeline_config(db, data.pipeline_id)
            if pipeline is None:
                raise DomainException(
                    f"Pipeline with id={data.pipeline_id} not found",
                    status_code=404,
                )

        # ── Create ─────────────────────────────────────────────────────
        group = SyncGroup(
            name=data.name,
            description=data.description,
            pipeline_id=data.pipeline_id,
            sync_cron=data.sync_cron,
            sync_enabled=data.sync_enabled,
            sync_concurrency=data.sync_concurrency,
            freshness_cron=data.freshness_cron,
            freshness_enabled=data.freshness_enabled,
            freshness_concurrency=data.freshness_concurrency,
        )
        db.add(group)
        await db.flush()

        # ── Audit ──────────────────────────────────────────────────────
        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="sync_group.created",
            resource_type="sync_group",
            resource_id=group.id,
            resource_name=group.name,
            details={
                "name": group.name,
                "description": group.description,
                "pipeline_id": group.pipeline_id,
            },
        )

        await db.commit()
        await db.refresh(group)
        logger.info("Created SyncGroup id=%d name='%s'", group.id, group.name)
        return group

    # ── Read (list) ────────────────────────────────────────────────────

    @staticmethod
    async def get_sync_groups(
        db: AsyncSession,
        user: User,
    ) -> list[SyncGroup]:
        """List sync groups with RBAC-scoped filtering.

        ADMIN users see everything.  Other users see only the sync groups
        whose IDs are referenced by their role’s ``RoleScopeSyncGroup``
        entries.

        Returns:
            List of SyncGroup (sorted by *name*), each with ``pipeline``
            eagerly loaded and ``mirrors`` eagerly loaded for counting.
        """
        # ── RBAC scope resolution ──────────────────────────────────────
        user_role_ids: list[int] = [ur.role_id for ur in user.user_roles]

        is_admin_result = await db.execute(
            select(Role.name).where(
                Role.id.in_(user_role_ids),
                Role.name == "admin",
            )
        )
        is_admin = is_admin_result.scalar_one_or_none() is not None

        # Build base query
        base_query = (
            select(SyncGroup)
            .options(
                selectinload(SyncGroup.pipeline),
                selectinload(SyncGroup.mirrors),
            )
            .where(~SyncGroup.is_deleted)
        )

        if not is_admin and user_role_ids:
            sync_scope_result = await db.execute(
                select(RoleScopeSyncGroup.sync_group_id).where(
                    RoleScopeSyncGroup.role_id.in_(user_role_ids)
                )
            )
            allowed_sync_group_ids = {row[0] for row in sync_scope_result}

            if allowed_sync_group_ids:
                base_query = base_query.where(SyncGroup.id.in_(allowed_sync_group_ids))
            else:
                return []

        base_query = base_query.order_by(SyncGroup.name.asc())

        result = await db.execute(base_query)
        groups = list(result.unique().scalars().all())
        return groups

    # ── Read (detail) ──────────────────────────────────────────────────

    @staticmethod
    async def get_sync_group(
        db: AsyncSession,
        group_id: int,
    ) -> SyncGroup:
        """Return a single sync group by ID with mirrors and pipeline
        eagerly loaded.

        Args:
            db: Async database session.
            group_id: ID of the sync group to fetch.

        Returns:
            SyncGroup with ``pipeline`` and ``mirrors`` eagerly loaded.

        Raises:
            DomainException: When no non-deleted group with *group_id*
                             exists (404).
        """
        result = await db.execute(
            select(SyncGroup)
            .options(
                selectinload(SyncGroup.pipeline),
                selectinload(SyncGroup.mirrors),
            )
            .where(SyncGroup.id == group_id, ~SyncGroup.is_deleted)
        )
        group = result.scalar_one_or_none()

        if group is None:
            raise DomainException(
                f"SyncGroup with id={group_id} not found",
                status_code=404,
            )
        return group

    # ── Update ─────────────────────────────────────────────────────────

    @staticmethod
    async def update_sync_group(
        db: AsyncSession,
        group_id: int,
        data: SyncGroupUpdate,
        user_id: int | None = None,
        username: str = "system",
    ) -> SyncGroup:
        """Update a sync group’s metadata (description, pipeline_id, and
        schedule fields).

        Args:
            db: Async database session.
            group_id: ID of the sync group to update.
            data: Partial update payload (``SyncGroupUpdate``).
            user_id: ID of the user performing the action.
            username: Username for audit logging (default ``"system"``).

        Returns:
            The updated SyncGroup with ``pipeline`` eagerly loaded.

        Raises:
            DomainException: When the group is not found (404) or the
                             referenced pipeline does not exist (404).
        """
        # ── Fetch existing ─────────────────────────────────────────────
        result = await db.execute(
            select(SyncGroup)
            .options(selectinload(SyncGroup.pipeline))
            .where(SyncGroup.id == group_id, ~SyncGroup.is_deleted)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise DomainException(
                f"SyncGroup with id={group_id} not found",
                status_code=404,
            )

        # ── Validate pipeline if provided ──────────────────────────────
        if data.pipeline_id is not None:
            pipeline = await get_pipeline_config(db, data.pipeline_id)
            if pipeline is None:
                raise DomainException(
                    f"Pipeline with id={data.pipeline_id} not found",
                    status_code=404,
                )
            group.pipeline_id = data.pipeline_id

        # ── Apply updates ──────────────────────────────────────────────
        if data.description is not None:
            group.description = data.description
        if data.sync_cron is not None:
            group.sync_cron = data.sync_cron
        if data.sync_enabled is not None:
            group.sync_enabled = data.sync_enabled
        if data.sync_concurrency is not None:
            group.sync_concurrency = data.sync_concurrency
        if data.freshness_cron is not None:
            group.freshness_cron = data.freshness_cron
        if data.freshness_enabled is not None:
            group.freshness_enabled = data.freshness_enabled
        if data.freshness_concurrency is not None:
            group.freshness_concurrency = data.freshness_concurrency

        # ── Audit ──────────────────────────────────────────────────────
        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="sync_group.updated",
            resource_type="sync_group",
            resource_id=group.id,
            resource_name=group.name,
            details={
                "description": group.description,
                "pipeline_id": group.pipeline_id,
                "sync_enabled": group.sync_enabled,
            },
        )

        await db.commit()
        await db.refresh(group)
        logger.info("Updated SyncGroup id=%d", group.id)
        return group

    # ── Delete (soft) ──────────────────────────────────────────────────

    @staticmethod
    async def delete_sync_group(
        db: AsyncSession,
        group_id: int,
        user_id: int | None = None,
        username: str = "system",
    ) -> None:
        """Soft-delete a sync group and migrate its mirrors to the
        default group.

        Args:
            db: Async database session.
            group_id: ID of the sync group to delete.
            user_id: ID of the user performing the action.
            username: Username for audit logging (default ``"system"``).

        Raises:
            DomainException: When the group is not found (404) or when
                             attempting to delete the default group (400).
        """
        # ── Fetch group ────────────────────────────────────────────────
        result = await db.execute(
            select(SyncGroup)
            .options(
                selectinload(SyncGroup.mirrors),
            )
            .where(SyncGroup.id == group_id, ~SyncGroup.is_deleted)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise DomainException(
                f"SyncGroup with id={group_id} not found",
                status_code=404,
            )

        # ── Cannot delete default group ────────────────────────────────
        if group.is_default:
            raise DomainException(
                "Cannot delete the default sync group",
                status_code=400,
            )

        # ── Migrate mirrors to default group ───────────────────────────
        default_group = await SyncGroupService.get_default_group(db)

        migrated_count = 0
        for mirror in group.mirrors:
            if not mirror.is_deleted:
                mirror.sync_group_id = default_group.id
                migrated_count += 1

        # ── Soft-delete ────────────────────────────────────────────────
        group.is_deleted = True
        group.deleted_at = datetime.now(UTC)

        # ── Audit ──────────────────────────────────────────────────────
        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="sync_group.deleted",
            resource_type="sync_group",
            resource_id=group.id,
            resource_name=group.name,
            details={
                "migrated_mirrors_count": migrated_count,
                "target_default_group_id": default_group.id,
            },
        )

        await db.commit()
        logger.info(
            "Soft-deleted SyncGroup id=%d name='%s'; migrated %d mirrors to default group id=%d",
            group.id,
            group.name,
            migrated_count,
            default_group.id,
        )

    # ── Restore ─────────────────────────────────────────────────────────

    @staticmethod
    async def restore_sync_group(
        db: AsyncSession,
        group_id: int,
        user_id: int | None = None,
        username: str = "system",
    ) -> SyncGroup:
        """Restore a soft-deleted sync group.

        Args:
            db: Async database session.
            group_id: ID of the sync group to restore.
            user_id: ID of the user performing the action.
            username: Username for audit logging (default ``"system"``).

        Returns:
            The restored SyncGroup with ``pipeline`` eagerly loaded.

        Raises:
            DomainException: When no sync group with *group_id* exists
                             (including soft-deleted) (404).
        """
        result = await db.execute(
            select(SyncGroup)
            .options(
                selectinload(SyncGroup.pipeline),
                selectinload(SyncGroup.mirrors),
            )
            .where(SyncGroup.id == group_id)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise DomainException(
                f"SyncGroup with id={group_id} not found",
                status_code=404,
            )

        if not group.is_deleted:
            await db.refresh(group)
            return group  # already restored

        group.is_deleted = False
        group.deleted_at = None

        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="sync_group.restored",
            resource_type="sync_group",
            resource_id=group.id,
            resource_name=group.name,
        )

        await db.commit()
        await db.refresh(group)
        logger.info("Restored SyncGroup id=%d name='%s'", group.id, group.name)
        return group

    # ── Assign Mirrors ─────────────────────────────────────────────────

    @staticmethod
    async def assign_mirrors_to_group(
        db: AsyncSession,
        group_id: int,
        mirror_ids: list[int],
        user_id: int | None = None,
        username: str = "system",
    ) -> list[Mirror]:
        """Assign mirrors in bulk to a sync group.

        Updates ``sync_group_id`` on every mirror whose ID appears in
        *mirror_ids*.  Mirrors that are already soft-deleted are skipped.

        Args:
            db: Async database session.
            group_id: ID of the target sync group.
            mirror_ids: List of mirror IDs to assign.
            user_id: ID of the user performing the action.
            username: Username for audit logging (default ``"system"``).

        Returns:
            List of Mirror instances that were updated.

        Raises:
            DomainException: When *group_id* does not reference an
                             existing, non-deleted sync group (404).
        """
        # ── Validate group exists ──────────────────────────────────────
        group_result = await db.execute(
            select(SyncGroup).where(
                SyncGroup.id == group_id,
                ~SyncGroup.is_deleted,
            )
        )
        if group_result.scalar_one_or_none() is None:
            raise DomainException(
                f"SyncGroup with id={group_id} not found",
                status_code=404,
            )

        if not mirror_ids:
            return []

        # ── Fetch non-deleted mirrors ──────────────────────────────────
        result = await db.execute(
            select(Mirror).where(
                Mirror.id.in_(mirror_ids),
                ~Mirror.is_deleted,
            )
        )
        mirrors = list(result.scalars().all())
        updated_mirrors: list[Mirror] = []

        for mirror in mirrors:
            mirror.sync_group_id = group_id
            updated_mirrors.append(mirror)

        # ── Audit ──────────────────────────────────────────────────────
        name = None
        group_name_result = await db.execute(select(SyncGroup.name).where(SyncGroup.id == group_id))
        row = group_name_result.scalar_one_or_none()
        if row:
            name = row

        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="sync_group.mirrors_assigned",
            resource_type="sync_group",
            resource_id=group_id,
            resource_name=name,
            details={
                "count": len(updated_mirrors),
                "mirror_ids": [m.id for m in updated_mirrors],
            },
        )

        await db.commit()

        # ── Refresh to get up-to-date state ────────────────────────────
        for mirror in updated_mirrors:
            await db.refresh(mirror)

        logger.info(
            "Assigned %d mirrors to SyncGroup id=%d",
            len(updated_mirrors),
            group_id,
        )
        return updated_mirrors

    # ── Bulk Assign Mirrors (validated) ─────────────────────────────────

    @staticmethod
    async def bulk_assign_mirrors(
        db: AsyncSession,
        sync_group_id: int,
        mirror_ids: list[int],
        user_id: int | None = None,
        username: str = "system",
    ) -> SyncGroup:
        """Assign multiple mirrors to a SyncGroup in bulk.

        Compared to :meth:`assign_mirrors_to_group`, this method:
        * Validates that **every** mirror ID in *mirror_ids* exists
          (raises ``ValueError`` for missing IDs).
        * Is **idempotent** — mirrors already in the target group are
          skipped rather than re-assigned.
        * Moves mirrors that belong to *other* groups into this group.
        * Returns the refreshed :class:`SyncGroup` with ``pipeline``
          and ``mirrors`` eagerly loaded, instead of a list of mirrors.

        Args:
            db: Async database session.
            sync_group_id: ID of the target SyncGroup.
            mirror_ids: List of mirror IDs to assign (non-empty).
            user_id: ID of the user performing the action.
            username: Username for audit logging (default ``"system"``).

        Returns:
            The SyncGroup with ``pipeline`` and ``mirrors`` eagerly loaded.

        Raises:
            DomainException: When *sync_group_id* does not reference an
                             existing, non-deleted sync group (404).
            ValueError: When one or more IDs in *mirror_ids* do not match
                       any non-deleted Mirror.
        """
        # ── Validate group exists ───────────────────────────────────────
        group_result = await db.execute(
            select(SyncGroup)
            .options(selectinload(SyncGroup.pipeline))
            .where(
                SyncGroup.id == sync_group_id,
                ~SyncGroup.is_deleted,
            )
        )
        group = group_result.scalar_one_or_none()
        if group is None:
            raise DomainException(
                f"SyncGroup with id={sync_group_id} not found",
                status_code=404,
            )

        if not mirror_ids:
            await db.refresh(group)
            return group

        # ── Fetch all requested mirrors ─────────────────────────────────
        result = await db.execute(
            select(Mirror).where(
                Mirror.id.in_(mirror_ids),
                ~Mirror.is_deleted,
            )
        )
        mirrors_map: dict[int, Mirror] = {m.id: m for m in result.scalars().all()}

        # ── Validate all mirror IDs exist ───────────────────────────────
        missing = set(mirror_ids) - set(mirrors_map.keys())
        if missing:
            raise ValueError(f"Mirrors not found: {missing}")

        # ── Assign mirrors (idempotent — skip already assigned) ─────────
        assigned_count = 0
        moved_count = 0
        for mirror_id in mirror_ids:
            mirror = mirrors_map[mirror_id]
            if mirror.sync_group_id == sync_group_id:
                continue  # already in this group — idempotent
            if mirror.sync_group_id is not None:
                moved_count += 1
            mirror.sync_group_id = sync_group_id
            assigned_count += 1

        # ── Audit ──────────────────────────────────────────────────────
        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="sync_group.mirrors_bulk_assigned",
            resource_type="sync_group",
            resource_id=group.id,
            resource_name=group.name,
            details={
                "assigned_count": assigned_count,
                "moved_count": moved_count,
                "skipped_count": len(mirror_ids) - assigned_count,
                "mirror_ids": mirror_ids,
            },
        )

        await db.commit()
        await db.refresh(group)

        logger.info(
            "Bulk assigned %d mirrors to SyncGroup id=%d (moved=%d, skipped=%d)",
            assigned_count,
            sync_group_id,
            moved_count,
            len(mirror_ids) - assigned_count,
        )
        return group

    # ── Apply Pipeline ─────────────────────────────────────────────────

    @staticmethod
    async def apply_pipeline(
        db: AsyncSession,
        sync_group_id: int,
        pipeline_id: int,
        user_id: int | None = None,
        username: str = "system",
    ) -> SyncGroup:
        """Apply a Pipeline configuration to a SyncGroup.

        Updates the SyncGroup's ``pipeline_id`` and returns the updated
        group with ``pipeline`` eagerly loaded.

        Args:
            db: Async database session.
            sync_group_id: ID of the sync group to update.
            pipeline_id: ID of the pipeline to apply.
            user_id: ID of the user performing the action.
            username: Username for audit logging (default ``"system"``).

        Returns:
            The updated SyncGroup with ``pipeline`` eagerly loaded.

        Raises:
            DomainException: When the sync group is not found (404) or the
                             referenced pipeline does not exist (404).
        """
        # ── Fetch existing group ───────────────────────────────────────
        result = await db.execute(
            select(SyncGroup)
            .options(selectinload(SyncGroup.pipeline))
            .where(
                SyncGroup.id == sync_group_id,
                ~SyncGroup.is_deleted,
            )
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise DomainException(
                f"SyncGroup with id={sync_group_id} not found",
                status_code=404,
            )

        # ── Validate pipeline exists ───────────────────────────────────
        pipeline = await get_pipeline_config(db, pipeline_id)
        if pipeline is None:
            raise DomainException(
                f"Pipeline with id={pipeline_id} not found",
                status_code=404,
            )

        # ── Apply update ───────────────────────────────────────────────
        group.pipeline_id = pipeline_id

        # ── Audit ──────────────────────────────────────────────────────
        await AuditService.log_event(
            db,
            user_id=user_id,
            username=username,
            action="sync_group.pipeline_applied",
            resource_type="sync_group",
            resource_id=group.id,
            resource_name=group.name,
            details={
                "previous_pipeline_id": group.pipeline_id,
                "new_pipeline_id": pipeline_id,
            },
        )

        await db.commit()
        await db.refresh(group)

        logger.info(
            "Applied Pipeline id=%d to SyncGroup id=%d name='%s'",
            pipeline_id,
            group.id,
            group.name,
        )
        return group

    # ── Active Groups (for scheduler) ──────────────────────────────────

    @staticmethod
    async def get_active_sync_groups(db: AsyncSession) -> list[SyncGroup]:
        """Return all SyncGroups that have either sync or freshness enabled.

        Used by SyncScheduler to discover which groups need scheduled jobs.

        Args:
            db: Async database session.

        Returns:
            List of SyncGroup with ``pipeline`` eagerly loaded.
        """
        result = await db.execute(
            select(SyncGroup)
            .options(selectinload(SyncGroup.pipeline))
            .where(
                ~SyncGroup.is_deleted,
                (SyncGroup.sync_enabled) | (SyncGroup.freshness_enabled),
            )
        )
        return list(result.unique().scalars().all())
