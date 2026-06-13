"""
@file pipeline.py
@description Business logic for managing GitLab pipeline runs and CI/CD components.
             Uses python-gitlab to interact with GitLab API for triggering,
             cancelling, and retrying pipelines.
@dependencies python-gitlab, app.core.secrets (decrypt_secret),
              app.core.exceptions (domain exceptions)
@relatedFiles ../models/pipeline_run.py, ../models/gitlab_component.py,
              ../../schemas/pipeline.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import gitlab
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import BadRequestError, DomainException, NotFoundError
from app.core.secrets import decrypt_secret
from app.models.gitlab_component import GitLabComponent
from app.models.gitlab_instance import GitlabInstance as GitlabInstanceModel
from app.models.pipeline import Pipeline, PipelineComponent
from app.models.pipeline_run import PipelineRun
from app.models.sync_group import SyncGroup

# ---------------------------------------------------------------------------
# Status flag constants (unified across the platform)
# ---------------------------------------------------------------------------
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


# ===================================================================
# Helpers
# ===================================================================


def _get_gitlab_client(instance: GitlabInstanceModel) -> gitlab.Gitlab:
    """Create a python-gitlab client for the given instance."""
    token = decrypt_secret(instance.token)
    return gitlab.Gitlab(
        url=instance.url,
        private_token=token,
        ssl_verify=instance.verify_ssl,
        user_agent="BigBug/1.0",
    )


async def _get_instance_or_404(db: AsyncSession, instance_id: int) -> GitlabInstanceModel:
    """Fetch a GitLab instance by id or raise NotFoundError."""
    result = await db.execute(
        select(GitlabInstanceModel).where(GitlabInstanceModel.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise NotFoundError(f"GitLab instance with id={instance_id} not found")
    return instance


async def _get_run_or_404(db: AsyncSession, run_id: int) -> PipelineRun:
    """Fetch a PipelineRun by id or raise NotFoundError."""
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError(f"Pipeline run with id={run_id} not found")
    return run


async def _get_component_or_404(db: AsyncSession, component_id: int) -> GitLabComponent:
    """Fetch a GitLabComponent by id or raise NotFoundError."""
    result = await db.execute(select(GitLabComponent).where(GitLabComponent.id == component_id))
    component = result.scalar_one_or_none()
    if component is None:
        raise NotFoundError(f"GitLab component with id={component_id} not found")
    return component


def _validate_component_inputs(
    schema: dict[str, Any],
    inputs: dict[str, Any],
    component_name: str,
) -> None:
    """Validate *inputs* against the component's *inputs_schema* (JSON Schema subset).

    Raises :class:`BadRequestError` when required fields are missing or types
    don't match.
    """
    properties: dict[str, dict[str, Any]] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])

    # 1. Missing required fields
    for field in required:
        if field not in inputs:
            raise BadRequestError(
                f"Missing required input '{field}' for component '{component_name}'"
            )

    # 2. Simple type checks for supplied inputs
    for key, value in inputs.items():
        if key not in properties:
            continue
        prop = properties[key]
        expected_type = prop.get("type")
        if expected_type is None:
            continue
        try:
            _check_json_type(key, value, expected_type)
        except ValueError as exc:
            raise BadRequestError(
                f"Invalid type for input '{key}' of component '{component_name}': {exc}"
            ) from exc


_SIMPLE_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _check_json_type(name: str, value: Any, json_type: str) -> None:
    """Raise :class:`ValueError` when *value* is not compatible with *json_type*."""
    expected = _SIMPLE_TYPE_MAP.get(json_type)
    if expected is None:
        return  # unknown type — skip check

    # Allow null for optional fields
    if value is None:
        return

    if not isinstance(value, expected):
        raise ValueError(f"expected {json_type}, got {type(value).__name__}")


# ===================================================================
# Pipeline Runs
# ===================================================================


async def trigger_pipeline(
    db: AsyncSession,
    gitlab_instance_id: int,
    gitlab_project_id: int,
    ref: str,
    variables: dict[str, str] | None = None,
    user_id: int | None = None,
) -> PipelineRun:
    """Trigger a GitLab pipeline via the API and record it in the database."""
    instance = await _get_instance_or_404(db, gitlab_instance_id)
    gl = _get_gitlab_client(instance)

    # Convert variables dict to GitLab API format
    gl_variables: list[dict[str, str]] = []
    if variables:
        for key, value in variables.items():
            gl_variables.append({"key": key, "value": value})

    # Trigger pipeline via GitLab API
    try:
        project = gl.projects.get(gitlab_project_id)
        pipeline_data = {
            "ref": ref,
        }
        if gl_variables:
            pipeline_data["variables"] = gl_variables
        gl_pipeline = project.pipelines.create(pipeline_data)
    except gitlab.GitlabError as exc:
        # Record a failed attempt in the database
        run = PipelineRun(
            gitlab_instance_id=gitlab_instance_id,
            gitlab_project_id=gitlab_project_id,
            ref=ref,
            variables=variables or {},
            trigger_type="manual",
            triggered_by_user_id=user_id,
            status_flag=STATUS_FAILED,
            status_text=f"GitLab API error: {exc}",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    # Record the pipeline run
    run = PipelineRun(
        gitlab_instance_id=gitlab_instance_id,
        gitlab_project_id=gitlab_project_id,
        gitlab_pipeline_id=gl_pipeline.id,
        ref=ref,
        variables=variables or {},
        trigger_type="manual",
        triggered_by_user_id=user_id,
        status_flag=STATUS_IN_PROGRESS,
        status_text="Running",
        web_url=gl_pipeline.web_url,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def trigger_pipeline_from_config(
    db: AsyncSession,
    pipeline: Pipeline,
    gitlab_project_id: int,
    mirror_variables: dict[str, str] | None = None,
    user_id: int | None = None,
) -> PipelineRun:
    """Trigger a GitLab CI/CD pipeline using a Pipeline configuration and mirror context.

    Loads the pipeline's gitlab_instance relationship, merges default variables
    with mirror-specific variables (mirror overrides defaults), creates a
    PipelineRun record, and calls the GitLab API to actually start the pipeline.

    Args:
        db: Database session.
        pipeline: Pipeline configuration (must have ``gitlab_instance`` loaded).
        gitlab_project_id: Target GitLab project ID (from Mirror).
        mirror_variables: Mirror-specific variables (SOURCE_URL, TARGET_PATH, …).
        user_id: ID of the user triggering the pipeline (for audit).

    Returns:
        The created :class:`PipelineRun` record.

    Raises:
        BadRequestError: If the pipeline is disabled.
        NotFoundError: If the pipeline has no gitlab_instance.
    """
    # -- Guard: pipeline must be enabled and have a GitLab instance ----------
    if not pipeline.is_enabled:
        raise BadRequestError(f"Pipeline '{pipeline.name}' is disabled")

    if not pipeline.gitlab_instance:
        raise NotFoundError(
            f"Pipeline '{pipeline.name}' has no gitlab_instance assigned"
        )

    # -- Merge variables: defaults → mirror overrides -----------------------
    variables: dict[str, str] = dict(pipeline.default_variables or {})
    if mirror_variables:
        variables.update(mirror_variables)

    ref = pipeline.ref or "main"
    instance = pipeline.gitlab_instance
    gl = _get_gitlab_client(instance)

    # Convert variables to python-gitlab format
    gl_variables: list[dict[str, str]] = []
    if variables:
        for key, value in variables.items():
            gl_variables.append({"key": key, "value": value})

    # -- Trigger pipeline via GitLab API ------------------------------------
    try:
        project = gl.projects.get(gitlab_project_id)
        pipeline_data: dict[str, Any] = {"ref": ref}
        if gl_variables:
            pipeline_data["variables"] = gl_variables
        gl_pipeline = project.pipelines.create(pipeline_data)
    except gitlab.GitlabError as exc:
        run = PipelineRun(
            pipeline_id=pipeline.id,
            gitlab_instance_id=instance.id,
            gitlab_project_id=gitlab_project_id,
            ref=ref,
            variables=variables,
            trigger_type="manual",
            triggered_by_user_id=user_id,
            status_flag=STATUS_FAILED,
            status_text=f"GitLab API error: {exc}",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    # -- Record the successful pipeline run ---------------------------------
    run = PipelineRun(
        pipeline_id=pipeline.id,
        gitlab_instance_id=instance.id,
        gitlab_project_id=gitlab_project_id,
        gitlab_pipeline_id=gl_pipeline.id,
        ref=ref,
        variables=variables,
        trigger_type="manual",
        triggered_by_user_id=user_id,
        status_flag=STATUS_IN_PROGRESS,
        status_text="Running",
        web_url=gl_pipeline.web_url,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def monitor_pipeline_status(
    db: AsyncSession,
    pipeline_run_id: int,
) -> PipelineRun:
    """Poll GitLab API for the current status of a PipelineRun.

    Fetches the pipeline status from GitLab and updates the PipelineRun
    record accordingly (status_flag, status_text, finished_at, duration,
    web_url).

    Args:
        db: Database session.
        pipeline_run_id: ID of the :class:`PipelineRun` to monitor.

    Returns:
        The updated :class:`PipelineRun`.

    Raises:
        NotFoundError: If the PipelineRun does not exist.
        BadRequestError: If the PipelineRun has no ``gitlab_pipeline_id``.
    """
    run = await _get_run_or_404(db, pipeline_run_id)

    if not run.gitlab_pipeline_id:
        raise BadRequestError(
            f"PipelineRun {pipeline_run_id} has no gitlab_pipeline_id — "
            "cannot monitor status"
        )

    instance = await _get_instance_or_404(db, run.gitlab_instance_id)
    gl = _get_gitlab_client(instance)

    # -- Fetch status from GitLab API ---------------------------------------
    try:
        project = gl.projects.get(run.gitlab_project_id)
        gl_pipeline = project.pipelines.get(run.gitlab_pipeline_id)
    except gitlab.GitlabError as exc:
        run.status_flag = STATUS_WARNING
        run.status_text = f"GitLab API error while monitoring: {exc}"
        await db.commit()
        await db.refresh(run)
        return run

    # -- Map GitLab status to internal status flag --------------------------
    gl_status = getattr(gl_pipeline, "status", "").lower()
    new_flag = GITLAB_STATUS_MAP.get(gl_status, STATUS_PENDING)

    run.status_flag = new_flag
    run.status_text = gl_status.capitalize() if gl_status else "Unknown"

    # Update optional fields from GitLab response
    gl_web_url = getattr(gl_pipeline, "web_url", None)
    if gl_web_url:
        run.web_url = gl_web_url

    gl_duration = getattr(gl_pipeline, "duration", None)
    if gl_duration is not None:
        run.duration = gl_duration

    # Set started_at when the pipeline transitions to running
    if gl_status == "running" and run.started_at is None:
        run.started_at = datetime.now(UTC)

    # Set finished_at when the pipeline reaches a terminal state
    if gl_status in ("success", "failed", "canceled"):
        run.finished_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(run)
    return run


async def cancel_pipeline(db: AsyncSession, run_id: int) -> PipelineRun:
    """Cancel a running GitLab pipeline."""
    run = await _get_run_or_404(db, run_id)

    if run.gitlab_pipeline_id is None:
        run.status_flag = STATUS_FAILED
        run.status_text = "Cannot cancel — no GitLab pipeline ID"
        await db.commit()
        await db.refresh(run)
        return run

    instance = await _get_instance_or_404(db, run.gitlab_instance_id)
    gl = _get_gitlab_client(instance)

    try:
        project = gl.projects.get(run.gitlab_project_id)
        gl_pipeline = project.pipelines.get(run.gitlab_pipeline_id)
        gl_pipeline.cancel()
    except gitlab.GitlabError as exc:
        run.status_flag = STATUS_WARNING
        run.status_text = f"Cancel failed: {exc}"
        await db.commit()
        await db.refresh(run)
        return run

    run.status_flag = STATUS_FAILED
    run.status_text = "Canceled"
    run.finished_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(run)
    return run


async def retry_pipeline(db: AsyncSession, run_id: int) -> PipelineRun:
    """Retry a failed GitLab pipeline."""
    run = await _get_run_or_404(db, run_id)

    if run.gitlab_pipeline_id is None:
        # Create a new pipeline run entry since we can't retry without a GitLab ID
        run.status_flag = STATUS_FAILED
        run.status_text = "Cannot retry — no GitLab pipeline ID"
        await db.commit()
        await db.refresh(run)
        return run

    instance = await _get_instance_or_404(db, run.gitlab_instance_id)
    gl = _get_gitlab_client(instance)

    try:
        project = gl.projects.get(run.gitlab_project_id)
        gl_pipeline = project.pipelines.get(run.gitlab_pipeline_id)
        gl_pipeline.retry()
    except gitlab.GitlabError as exc:
        run.status_flag = STATUS_WARNING
        run.status_text = f"Retry failed: {exc}"
        await db.commit()
        await db.refresh(run)
        return run

    run.status_flag = STATUS_IN_PROGRESS
    run.status_text = "Running"
    run.started_at = datetime.now(UTC)
    run.finished_at = None
    run.duration = None
    await db.commit()
    await db.refresh(run)
    return run


async def get_pipeline_runs(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: int | None = None,
) -> tuple[list[PipelineRun], int]:
    """Get paginated list of pipeline runs with optional status filter."""
    # Count query
    count_q = select(func.count()).select_from(PipelineRun)
    if status_filter is not None:
        count_q = count_q.where(PipelineRun.status_flag == status_filter)
    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    # Data query
    q = select(PipelineRun).order_by(PipelineRun.created_at.desc())
    if status_filter is not None:
        q = q.where(PipelineRun.status_flag == status_filter)
    q = q.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(q)
    items = list(result.scalars().all())

    return items, total


async def get_pipeline_run(db: AsyncSession, run_id: int) -> PipelineRun:
    """Get a single pipeline run by id."""
    return await _get_run_or_404(db, run_id)


async def update_pipeline_status(
    db: AsyncSession,
    gitlab_pipeline_id: int,
    status: str,
    web_url: str | None = None,
    duration: int | None = None,
) -> PipelineRun | None:
    """Update pipeline run status from webhook payload data."""
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.gitlab_pipeline_id == gitlab_pipeline_id)
    )
    run = result.scalars().first()

    if run is None:
        return None

    run.status_flag = GITLAB_STATUS_MAP.get(status, STATUS_PENDING)
    run.status_text = status.capitalize() if status else "Unknown"

    if web_url:
        run.web_url = web_url

    if duration is not None:
        run.duration = duration

    if status in ("success", "failed", "canceled"):
        run.finished_at = datetime.now(UTC)
    elif status == "running" and run.started_at is None:
        run.started_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(run)
    return run


async def trigger_component(
    db: AsyncSession,
    component_id: int,
    inputs: dict[str, Any],
    ref: str = "main",
    user_id: int | None = None,
) -> PipelineRun:
    """Trigger a GitLab pipeline using a registered CI/CD component.

    1. Look up the :class:`GitLabComponent` by *component_id*.
    2. Validate *inputs* against the component's ``inputs_schema``.
    3. Find the GitLab project via the component's ``project_path``.
    4. Trigger a pipeline in that project, passing the validated inputs
       as CI/CD variables.
    5. Persist the run in :class:`PipelineRun` with *component_id* set.

    On any GitLab API failure a ``FAILED`` pipeline run is still recorded so
    the error is visible in the UI.
    """
    component = await _get_component_or_404(db, component_id)

    # -- Validate inputs ---------------------------------------------------
    if component.inputs_schema:
        _validate_component_inputs(component.inputs_schema, inputs, component.name)

    # -- Connect to GitLab and resolve the project --------------------------
    instance = await _get_instance_or_404(db, component.gitlab_instance_id)
    gl = _get_gitlab_client(instance)

    # Convert variables to python-gitlab format
    gl_variables: list[dict[str, str]] = [
        {"key": k, "value": str(v)} for k, v in inputs.items()
    ]

    try:
        project = gl.projects.get(component.project_path)
    except gitlab.GitlabError as exc:
        run = PipelineRun(
            gitlab_instance_id=component.gitlab_instance_id,
            gitlab_project_id=0,
            component_id=component_id,
            ref=ref,
            variables=inputs,
            trigger_type="manual",
            triggered_by_user_id=user_id,
            status_flag=STATUS_FAILED,
            status_text=f"GitLab project '{component.project_path}' not found: {exc}",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    # -- Trigger the pipeline ----------------------------------------------
    pipeline_data: dict[str, Any] = {"ref": ref}
    if gl_variables:
        pipeline_data["variables"] = gl_variables

    try:
        gl_pipeline = project.pipelines.create(pipeline_data)
    except gitlab.GitlabError as exc:
        run = PipelineRun(
            gitlab_instance_id=component.gitlab_instance_id,
            gitlab_project_id=project.id,
            component_id=component_id,
            ref=ref,
            variables=inputs,
            trigger_type="manual",
            triggered_by_user_id=user_id,
            status_flag=STATUS_FAILED,
            status_text=f"GitLab API error: {exc}",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        return run

    # -- Record the successful run -----------------------------------------
    run = PipelineRun(
        gitlab_instance_id=component.gitlab_instance_id,
        gitlab_project_id=project.id,
        gitlab_pipeline_id=gl_pipeline.id,
        component_id=component_id,
        ref=ref,
        variables=inputs,
        trigger_type="manual",
        triggered_by_user_id=user_id,
        status_flag=STATUS_IN_PROGRESS,
        status_text="Running",
        web_url=gl_pipeline.web_url,
        started_at=datetime.now(UTC),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


# ===================================================================
# GitLab Components
# ===================================================================


async def list_components(db: AsyncSession) -> list[GitLabComponent]:
    """List all registered GitLab CI/CD components."""
    result = await db.execute(select(GitLabComponent).order_by(GitLabComponent.name))
    return list(result.scalars().all())


async def get_component(db: AsyncSession, component_id: int) -> GitLabComponent:
    """Get a single GitLab component by id."""
    return await _get_component_or_404(db, component_id)


async def create_component(
    db: AsyncSession,
    name: str,
    gitlab_instance_id: int,
    project_path: str,
    component_path: str,
    description: str | None = None,
    version: str | None = None,
    inputs_schema: dict[str, Any] | None = None,
) -> GitLabComponent:
    """Register a new GitLab CI/CD component."""
    component = GitLabComponent(
        name=name,
        description=description,
        gitlab_instance_id=gitlab_instance_id,
        project_path=project_path,
        component_path=component_path,
        version=version,
        inputs_schema=inputs_schema,
        is_enabled=True,
    )
    db.add(component)
    await db.commit()
    await db.refresh(component)
    return component


async def update_component(
    db: AsyncSession,
    component_id: int,
    name: str | None = None,
    description: str | None = None,
    gitlab_instance_id: int | None = None,
    project_path: str | None = None,
    component_path: str | None = None,
    version: str | None = None,
    inputs_schema: dict[str, Any] | None = None,
    is_enabled: bool | None = None,
) -> GitLabComponent:
    """Update an existing GitLab component."""
    component = await _get_component_or_404(db, component_id)

    if name is not None:
        component.name = name
    if description is not None:
        component.description = description
    if gitlab_instance_id is not None:
        component.gitlab_instance_id = gitlab_instance_id
    if project_path is not None:
        component.project_path = project_path
    if component_path is not None:
        component.component_path = component_path
    if version is not None:
        component.version = version
    if inputs_schema is not None:
        component.inputs_schema = inputs_schema
    if is_enabled is not None:
        component.is_enabled = is_enabled

    component.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(component)
    return component


async def delete_component(db: AsyncSession, component_id: int) -> None:
    """Delete a GitLab component."""
    component = await _get_component_or_404(db, component_id)
    await db.delete(component)
    await db.commit()


# ===================================================================
# Pipeline Config CRUD (git-mirroring v2)
# ===================================================================

async def get_pipeline_configs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    is_enabled: bool | None = None,
    search: str | None = None,
) -> list[Pipeline]:
    """Return all Pipeline configs with eager-loaded components and gitlab_instance.

    Supports optional filtering by *is_enabled* and *search* (substring match on name).
    """
    stmt = select(Pipeline).options(
        joinedload(Pipeline.components).joinedload(PipelineComponent.component),
        joinedload(Pipeline.gitlab_instance),
    )

    if is_enabled is not None:
        stmt = stmt.where(Pipeline.is_enabled == is_enabled)
    if search:
        stmt = stmt.where(Pipeline.name.ilike(f"%{search}%"))

    stmt = stmt.order_by(Pipeline.name).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_pipeline_config(db: AsyncSession, pipeline_id: int) -> Pipeline | None:
    """Return a single Pipeline by ID with eager-loaded relations."""
    stmt = (
        select(Pipeline)
        .options(
            joinedload(Pipeline.components).joinedload(PipelineComponent.component),
            joinedload(Pipeline.gitlab_instance),
        )
        .where(Pipeline.id == pipeline_id)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def _unset_default(db: AsyncSession) -> None:
    """Set is_default=False on the Pipeline that currently holds it (if any)."""
    result = await db.execute(select(Pipeline).where(Pipeline.is_default == True))
    current = result.scalar_one_or_none()
    if current:
        current.is_default = False
        await db.flush()


async def _sync_components(db: AsyncSession, pipeline_id: int, components: list) -> None:
    """Delete existing PipelineComponent rows for *pipeline_id* and create new ones."""
    # delete existing
    result = await db.execute(
        select(PipelineComponent).where(PipelineComponent.pipeline_id == pipeline_id)
    )
    for pc in result.scalars().all():
        await db.delete(pc)
    await db.flush()

    # create new
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

    Raises :class:`DomainException` (409) when *name* already exists.
    """
    # uniqueness check
    result = await db.execute(select(Pipeline).where(Pipeline.name == data.name))
    if result.scalar_one_or_none() is not None:
        raise DomainException("Name already in use", status_code=409)

    pipeline = Pipeline(
        name=data.name,
        description=data.description,
        gitlab_instance_id=data.gitlab_instance_id,
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
        raise DomainException(f"Pipeline with id={pipeline_id} not found", status_code=404)

    # simple scalar fields
    if data.description is not None:
        pipeline.description = data.description
    if data.gitlab_instance_id is not None:
        pipeline.gitlab_instance_id = data.gitlab_instance_id
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


async def delete_pipeline(db: AsyncSession, pipeline_id: int) -> None:
    """Delete a Pipeline.

    Raises :class:`DomainException` (409) when:
    - the pipeline is the default one
    - the pipeline is referenced by any SyncGroup
    """
    pipeline = await get_pipeline_config(db, pipeline_id)
    if pipeline is None:
        raise DomainException(f"Pipeline with id={pipeline_id} not found", status_code=404)

    if pipeline.is_default:
        raise DomainException("Cannot delete default pipeline", status_code=409)

    # check SyncGroup references
    result = await db.execute(
        select(func.count()).select_from(SyncGroup).where(
            SyncGroup.pipeline_id == pipeline_id,
            SyncGroup.is_deleted == False,
        )
    )
    sync_count = result.scalar_one()
    if sync_count > 0:
        raise DomainException("Pipeline is in use by sync groups", status_code=409)

    # remove components
    result = await db.execute(
        select(PipelineComponent).where(PipelineComponent.pipeline_id == pipeline_id)
    )
    for pc in result.scalars().all():
        await db.delete(pc)

    await db.delete(pipeline)
    await db.commit()


async def duplicate_pipeline(db: AsyncSession, pipeline_id: int, new_name: str) -> Pipeline:
    """Duplicate a Pipeline under a new name.

    The copy inherits *is_enabled* but is forced to ``is_default=False``.
    """
    original = await get_pipeline_config(db, pipeline_id)
    if original is None:
        raise DomainException(f"Pipeline with id={pipeline_id} not found", status_code=404)

    # uniqueness check for new name
    result = await db.execute(select(Pipeline).where(Pipeline.name == new_name))
    if result.scalar_one_or_none() is not None:
        raise DomainException("Name already in use", status_code=409)

    new_pipeline = Pipeline(
        name=new_name,
        description=original.description,
        gitlab_instance_id=original.gitlab_instance_id,
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
    """Return the Pipeline marked as default (is_default=True)."""
    stmt = (
        select(Pipeline)
        .options(
            joinedload(Pipeline.components).joinedload(PipelineComponent.component),
            joinedload(Pipeline.gitlab_instance),
        )
        .where(Pipeline.is_default == True)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()
