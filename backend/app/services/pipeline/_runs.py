"""Pipeline run lifecycle: trigger, monitor, cancel, retry, query, webhook."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import gitlab
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.pipeline import Pipeline
from app.models.pipeline_run import PipelineRun
from app.services.pipeline._clients import (
    _get_client_for_run,
    _get_pipeline_provider_or_404,
    _get_provider_gitlab_client,
)
from app.services.pipeline._components import (
    _get_component_or_404,
    _validate_component_inputs,
)
from app.services.pipeline._status import (
    GITLAB_STATUS_MAP,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    STATUS_PENDING,
    STATUS_WARNING,
)


async def _get_run_or_404(db: AsyncSession, run_id: int) -> PipelineRun:
    """Fetch a PipelineRun by id or raise NotFoundError."""
    result = await db.execute(select(PipelineRun).where(PipelineRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundError(f"Pipeline run with id={run_id} not found")
    return run


async def trigger_pipeline(
    db: AsyncSession,
    gitlab_project_id: int,
    ref: str,
    variables: dict[str, str] | None = None,
    user_id: int | None = None,
    provider_id: int | None = None,
) -> PipelineRun:
    """Trigger a GitLab pipeline via the API and record it in the database.

    Providers V3 (11.3.4): ``provider_id`` must reference the system/internal
    gitlab ResourceProvider — the only provider allowed to trigger pipelines.
    """
    if provider_id is None:
        raise BadRequestError("trigger_pipeline requires provider_id")
    provider = await _get_pipeline_provider_or_404(db, provider_id)
    gl = _get_provider_gitlab_client(provider)
    connection_id: dict[str, int] = {"provider_id": provider.id}

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
            **connection_id,
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
        **connection_id,
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
    """Trigger a GitLab CI/CD pipeline using a Pipeline configuration and mirror context."""
    # -- Guard: pipeline must be enabled and have a provider -----------------
    if not pipeline.is_enabled:
        raise BadRequestError(f"Pipeline '{pipeline.name}' is disabled")

    ref = pipeline.ref or "main"

    # Providers V3 (11.3.4): the platform GitLab is a resource_providers row.
    provider = getattr(pipeline, "provider", None)
    connection_id: dict[str, int] = {}
    if provider is not None:
        gl = _get_provider_gitlab_client(provider)
        connection_id["provider_id"] = provider.id
    else:
        raise NotFoundError(f"Pipeline '{pipeline.name}' has no provider assigned")

    # -- Merge variables: defaults → mirror overrides -----------------------
    variables: dict[str, str] = dict(pipeline.default_variables or {})
    if mirror_variables:
        variables.update(mirror_variables)

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
            **connection_id,
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
        **connection_id,
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
    """Poll GitLab API for the current status of a PipelineRun."""
    run = await _get_run_or_404(db, pipeline_run_id)

    if not run.gitlab_pipeline_id:
        raise BadRequestError(
            f"PipelineRun {pipeline_run_id} has no gitlab_pipeline_id — cannot monitor status"
        )

    gl = await _get_client_for_run(db, run)

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

    gl = await _get_client_for_run(db, run)

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
        run.status_flag = STATUS_FAILED
        run.status_text = "Cannot retry — no GitLab pipeline ID"
        await db.commit()
        await db.refresh(run)
        return run

    gl = await _get_client_for_run(db, run)

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
    """Trigger a GitLab pipeline using a registered CI/CD component."""
    component = await _get_component_or_404(db, component_id)

    # -- Validate inputs ---------------------------------------------------
    if component.inputs_schema:
        _validate_component_inputs(component.inputs_schema, inputs, component.name)

    # -- Connect to GitLab and resolve the project --------------------------
    provider = await _get_pipeline_provider_or_404(db, component.provider_id)
    gl = _get_provider_gitlab_client(provider)

    # Convert variables to python-gitlab format
    gl_variables: list[dict[str, str]] = [{"key": k, "value": str(v)} for k, v in inputs.items()]

    try:
        project = gl.projects.get(component.project_path)
    except gitlab.GitlabError as exc:
        run = PipelineRun(
            provider_id=component.provider_id,
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
            provider_id=component.provider_id,
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
        provider_id=component.provider_id,
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
