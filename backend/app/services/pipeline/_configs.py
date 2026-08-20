"""Pipeline configuration CRUD (git-mirroring v2) + ``.gitlab-ci.yml`` push."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import DomainError
from app.models.gitlab_project import GitlabProject, GitlabProjectType
from app.models.pipeline import Pipeline, PipelineComponent
from app.models.resource_provider import ResourceProvider
from app.models.sync_group import SyncGroup
from app.models.user import User
from app.services.audit import AuditService
from app.services.gitlab_projects._service import GitlabProjectService
from app.services.pipeline._ci import generate_ci_from_pipeline
from app.services.pipeline._clients import _get_pipeline_provider_or_404

logger = logging.getLogger(__name__)


def _pipeline_eagerload_stmt():
    """Return a Pipeline select with components/provider/gitlab_project eager-loaded."""
    return select(Pipeline).options(
        joinedload(Pipeline.components).joinedload(PipelineComponent.component),
        joinedload(Pipeline.provider).joinedload(ResourceProvider.credential),
        joinedload(Pipeline.gitlab_project)
        .joinedload(GitlabProject.provider)
        .joinedload(ResourceProvider.credential),
    )


async def get_pipeline_configs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    is_enabled: bool | None = None,
    search: str | None = None,
) -> list[Pipeline]:
    """Return all Pipeline configs with eager-loaded components and provider.

    Supports optional filtering by *is_enabled* and *search* (substring match on name).
    """
    stmt = _pipeline_eagerload_stmt().where(~Pipeline.is_deleted)

    if is_enabled is not None:
        stmt = stmt.where(Pipeline.is_enabled == is_enabled)
    if search:
        stmt = stmt.where(Pipeline.name.ilike(f"%{search}%"))

    stmt = stmt.order_by(Pipeline.name).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_pipeline_config(db: AsyncSession, pipeline_id: int) -> Pipeline | None:
    """Return a single non-deleted Pipeline by ID with eager-loaded relations."""
    stmt = _pipeline_eagerload_stmt().where(Pipeline.id == pipeline_id, ~Pipeline.is_deleted)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def _unset_default(db: AsyncSession) -> None:
    """Set is_default=False on the non-deleted Pipeline that currently holds it (if any)."""
    result = await db.execute(select(Pipeline).where(Pipeline.is_default, ~Pipeline.is_deleted))
    current = result.scalar_one_or_none()
    if current:
        current.is_default = False
        await db.flush()


async def _sync_components(db: AsyncSession, pipeline_id: int, components: list) -> None:
    """Delete existing PipelineComponent rows for *pipeline_id* and create new ones."""
    result = await db.execute(
        select(PipelineComponent).where(PipelineComponent.pipeline_id == pipeline_id)
    )
    for pc in result.scalars().all():
        await db.delete(pc)
    await db.flush()

    for comp_ref in components:
        pc = PipelineComponent(
            pipeline_id=pipeline_id,
            component_id=comp_ref.component_id,
            order=comp_ref.order,
            overrides=comp_ref.overrides or {},
        )
        db.add(pc)


async def create_pipeline(db: AsyncSession, data) -> Pipeline:
    """Create a new Pipeline config.

    Raises :class:`DomainError` (409) when *name* already exists.
    """
    # uniqueness check (only among non-deleted pipelines)
    result = await db.execute(
        select(Pipeline).where(Pipeline.name == data.name, ~Pipeline.is_deleted)
    )
    if result.scalar_one_or_none() is not None:
        raise DomainError("Name already in use", status_code=409)

    # Providers V3: validate provider when supplied.
    if data.provider_id is not None:
        await _get_pipeline_provider_or_404(db, data.provider_id)

    # Bind to a pipelines gitlab project when supplied; derive provider_id.
    provider_id = data.provider_id
    gitlab_project_id = getattr(data, "gitlab_project_id", None)
    if gitlab_project_id is not None:
        project_svc = GitlabProjectService(db)
        project = await project_svc._get_project_or_404(gitlab_project_id)
        if project.project_type != GitlabProjectType.pipelines:
            raise DomainError("Pipeline must be linked to a pipelines project", 422)
        provider_id = project.provider_id
        if getattr(data, "ref", None) is None:
            data.ref = project.default_branch

    pipeline = Pipeline(
        name=data.name,
        description=data.description,
        provider_id=provider_id,
        gitlab_project_id=gitlab_project_id,
        ref=data.ref or "main",
        default_variables=data.default_variables or {},
        is_enabled=data.is_enabled,
    )

    # is_default handling
    if data.is_default is True:
        await _unset_default(db)

    pipeline.is_default = data.is_default if data.is_default is not None else False

    db.add(pipeline)
    await db.flush()

    # components
    if data.components:
        for comp_ref in data.components:
            pc = PipelineComponent(
                pipeline_id=pipeline.id,
                component_id=comp_ref.component_id,
                order=comp_ref.order,
                overrides=comp_ref.overrides or {},
            )
            db.add(pc)

    await db.commit()
    await db.refresh(pipeline)
    return await get_pipeline_config(db, pipeline.id)


async def update_pipeline(db: AsyncSession, pipeline_id: int, data) -> Pipeline:
    """Partial update of a Pipeline config."""
    pipeline = await get_pipeline_config(db, pipeline_id)
    if pipeline is None:
        raise DomainError(f"Pipeline with id={pipeline_id} not found", status_code=404)

    # simple scalar fields
    if data.description is not None:
        pipeline.description = data.description
    if data.provider_id is not None:
        # Providers V3: re-validate on every change.
        await _get_pipeline_provider_or_404(db, data.provider_id)
        pipeline.provider_id = data.provider_id
    if getattr(data, "gitlab_project_id", None) is not None:
        project_svc = GitlabProjectService(db)
        project = await project_svc._get_project_or_404(data.gitlab_project_id)
        if project.project_type != GitlabProjectType.pipelines:
            raise DomainError("Pipeline must be linked to a pipelines project", 422)
        pipeline.gitlab_project_id = project.id
        pipeline.provider_id = project.provider_id
    if data.ref is not None:
        pipeline.ref = data.ref
    if data.default_variables is not None:
        pipeline.default_variables = data.default_variables
    if data.is_enabled is not None:
        pipeline.is_enabled = data.is_enabled

    # is_default swap
    if data.is_default is not None and data.is_default is True:
        await _unset_default(db)
        pipeline.is_default = True

    # components replacement
    if data.components is not None:
        await _sync_components(db, pipeline_id, data.components)

    await db.commit()
    await db.refresh(pipeline)
    return await get_pipeline_config(db, pipeline_id)


async def delete_pipeline(
    db: AsyncSession,
    pipeline_id: int,
    username: str = "system",
) -> None:
    """Soft-delete a Pipeline.

    Raises :class:`DomainError` (409) when:
    - the pipeline is the default one
    - the pipeline is referenced by any active (non-deleted) SyncGroup
    """
    pipeline = await get_pipeline_config(db, pipeline_id)
    if pipeline is None:
        raise DomainError(f"Pipeline with id={pipeline_id} not found", status_code=404)

    if pipeline.is_default:
        raise DomainError("Cannot delete default pipeline", status_code=409)

    # check SyncGroup references (active, non-deleted groups only)
    result = await db.execute(
        select(func.count())
        .select_from(SyncGroup)
        .where(
            SyncGroup.pipeline_id == pipeline_id,
            ~SyncGroup.is_deleted,
        )
    )
    sync_count = result.scalar_one()
    if sync_count > 0:
        raise DomainError("Pipeline is in use by sync groups", status_code=409)

    pipeline.is_deleted = True
    pipeline.deleted_at = datetime.now(UTC)

    await AuditService.log_event(
        db,
        user_id=None,
        username=username,
        action="pipeline.deleted",
        resource_type="pipeline",
        resource_id=pipeline.id,
        resource_name=pipeline.name,
    )

    await db.commit()
    logger.info("Pipeline soft-deleted: id=%d name='%s'", pipeline_id, pipeline.name)


async def restore_pipeline(
    db: AsyncSession,
    pipeline_id: int,
    username: str = "system",
) -> Pipeline:
    """Restore a soft-deleted Pipeline."""
    result = await db.execute(_pipeline_eagerload_stmt().where(Pipeline.id == pipeline_id))
    pipeline = result.unique().scalar_one_or_none()
    if pipeline is None:
        raise DomainError(f"Pipeline with id={pipeline_id} not found", status_code=404)

    if not pipeline.is_deleted:
        await db.refresh(pipeline)
        return pipeline  # already restored

    pipeline.is_deleted = False
    pipeline.deleted_at = None

    await AuditService.log_event(
        db,
        user_id=None,
        username=username,
        action="pipeline.restored",
        resource_type="pipeline",
        resource_id=pipeline.id,
        resource_name=pipeline.name,
    )

    await db.commit()
    await db.refresh(pipeline)
    logger.info("Pipeline restored: id=%d name='%s'", pipeline_id, pipeline.name)
    return pipeline


async def duplicate_pipeline(db: AsyncSession, pipeline_id: int, new_name: str) -> Pipeline:
    """Duplicate a Pipeline under a new name.

    The copy inherits *is_enabled* but is forced to ``is_default=False``.
    """
    original = await get_pipeline_config(db, pipeline_id)
    if original is None:
        raise DomainError(f"Pipeline with id={pipeline_id} not found", status_code=404)

    # uniqueness check for new name (only among non-deleted pipelines)
    result = await db.execute(
        select(Pipeline).where(Pipeline.name == new_name, ~Pipeline.is_deleted)
    )
    if result.scalar_one_or_none() is not None:
        raise DomainError("Name already in use", status_code=409)

    new_pipeline = Pipeline(
        name=new_name,
        description=original.description,
        provider_id=original.provider_id,
        gitlab_project_id=original.gitlab_project_id,
        ref=original.ref,
        default_variables=original.default_variables,
        is_default=False,
        is_enabled=original.is_enabled,
    )
    db.add(new_pipeline)
    await db.flush()

    # copy components
    for orig_pc in original.components:
        pc = PipelineComponent(
            pipeline_id=new_pipeline.id,
            component_id=orig_pc.component_id,
            order=orig_pc.order,
            overrides=orig_pc.overrides or {},
        )
        db.add(pc)

    await db.commit()
    await db.refresh(new_pipeline)
    return await get_pipeline_config(db, new_pipeline.id)


async def get_default_pipeline(db: AsyncSession) -> Pipeline | None:
    """Return the non-deleted Pipeline marked as default (is_default=True)."""
    stmt = _pipeline_eagerload_stmt().where(Pipeline.is_default, ~Pipeline.is_deleted)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def push_pipeline_ci(
    db: AsyncSession,
    pipeline_id: int,
    user: User,
    commit_message: str | None = None,
    extra_yaml: str | None = None,
) -> dict[str, Any]:
    """Generate ``.gitlab-ci.yml`` from a Pipeline config and push it to its
    bound pipelines project (host-validated)."""
    from app.services.gitlab_projects._clients import get_provider_gitlab_client
    from app.services.gitlab_projects._files import upsert_file

    pipeline = await get_pipeline_config(db, pipeline_id)
    if pipeline is None:
        raise DomainError(f"Pipeline with id={pipeline_id} not found", status_code=404)

    project = pipeline.gitlab_project
    if project is None:
        raise DomainError(
            "Pipeline is not bound to a gitlab project — cannot push .gitlab-ci.yml",
            422,
        )

    project_svc = GitlabProjectService(db)
    await project_svc._ensure_can_mutate(project, user)

    yaml = generate_ci_from_pipeline(pipeline, extra_yaml=extra_yaml)

    provider = project.provider
    if provider is None:
        raise DomainError("Pipeline project has no provider", 404)
    gl = get_provider_gitlab_client(provider)
    result = await upsert_file(
        gl,
        project.full_path,
        ".gitlab-ci.yml",
        yaml,
        project.default_branch,
        commit_message or f"Push .gitlab-ci.yml for pipeline '{pipeline.name}'",
    )
    return {"pipeline_id": pipeline.id, "file_path": ".gitlab-ci.yml", **result}
