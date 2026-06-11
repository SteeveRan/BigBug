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

from app.core.exceptions import BadRequestError, NotFoundError
from app.core.secrets import decrypt_secret
from app.models.gitlab_component import GitLabComponent
from app.models.gitlab_instance import GitlabInstance as GitlabInstanceModel
from app.models.pipeline_run import PipelineRun

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
