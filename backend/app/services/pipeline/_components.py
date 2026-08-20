"""GitLab CI/CD component CRUD, push/pull and input validation helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import BadRequestError, DomainError, NotFoundError
from app.models.gitlab_component import GitLabComponent
from app.models.gitlab_project import GitlabProject, GitlabProjectType
from app.models.resource_provider import ResourceProvider
from app.models.user import User
from app.services.gitlab_projects._clients import get_provider_gitlab_client
from app.services.gitlab_projects._service import GitlabProjectService

_SIMPLE_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


async def _get_component_or_404(db: AsyncSession, component_id: int) -> GitLabComponent:
    """Fetch a GitLabComponent by id or raise NotFoundError."""
    result = await db.execute(select(GitLabComponent).where(GitLabComponent.id == component_id))
    component = result.scalar_one_or_none()
    if component is None:
        raise NotFoundError(f"GitLab component with id={component_id} not found")
    return component


async def _get_component_with_project(db: AsyncSession, component_id: int) -> GitLabComponent:
    """Fetch a component with its project + project provider eager-loaded."""
    result = await db.execute(
        select(GitLabComponent)
        .options(
            joinedload(GitLabComponent.gitlab_project)
            .joinedload(GitlabProject.provider)
            .joinedload(ResourceProvider.credential),
        )
        .where(GitLabComponent.id == component_id)
    )
    component = result.unique().scalar_one_or_none()
    if component is None:
        raise NotFoundError(f"GitLab component with id={component_id} not found")
    return component


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


async def list_components(
    db: AsyncSession, gitlab_project_id: int | None = None
) -> list[GitLabComponent]:
    """List registered GitLab CI/CD components, optionally filtered by project."""
    stmt = select(GitLabComponent)
    if gitlab_project_id is not None:
        stmt = stmt.where(GitLabComponent.gitlab_project_id == gitlab_project_id)
    result = await db.execute(stmt.order_by(GitLabComponent.name))
    return list(result.scalars().all())


def list_presets() -> list[dict[str, Any]]:
    """Return the embedded component template presets (key/name/description/schema)."""
    from app.services.gitlab_projects.presets import PRESETS, extract_inputs_schema

    return [
        {
            "key": key,
            "name": preset["name"],
            "description": preset["description"],
            "inputs_schema": extract_inputs_schema(preset["content"]),
        }
        for key, preset in PRESETS.items()
    ]


async def get_component(db: AsyncSession, component_id: int) -> GitLabComponent:
    """Get a single GitLab component by id."""
    return await _get_component_or_404(db, component_id)


async def create_component(
    db: AsyncSession,
    name: str,
    provider_id: int | None,
    project_path: str | None,
    component_path: str,
    description: str | None = None,
    version: str | None = None,
    inputs_schema: dict[str, Any] | None = None,
    gitlab_project_id: int | None = None,
) -> GitLabComponent:
    """Register a new GitLab CI/CD component.

    When ``gitlab_project_id`` is given the component is linked to that
    ``components`` project and ``provider_id``/``project_path`` are derived from
    it (input values are ignored for those two fields).
    """
    resolved_provider_id = provider_id
    resolved_project_path = project_path
    if gitlab_project_id is not None:
        project_svc = GitlabProjectService(db)
        project = await project_svc._get_project_or_404(gitlab_project_id)
        if project.project_type != GitlabProjectType.components:
            raise DomainError("Component must be linked to a components project", 422)
        resolved_provider_id = project.provider_id
        resolved_project_path = project.full_path

    if resolved_provider_id is None or resolved_project_path is None:
        raise BadRequestError(
            "provider_id and project_path are required when no gitlab_project_id is given"
        )

    component = GitLabComponent(
        name=name,
        description=description,
        provider_id=resolved_provider_id,
        project_path=resolved_project_path,
        component_path=component_path,
        version=version,
        inputs_schema=inputs_schema,
        gitlab_project_id=gitlab_project_id,
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
    provider_id: int | None = None,
    project_path: str | None = None,
    component_path: str | None = None,
    version: str | None = None,
    inputs_schema: dict[str, Any] | None = None,
    is_enabled: bool | None = None,
    gitlab_project_id: int | None = None,
) -> GitLabComponent:
    """Update an existing GitLab component."""
    component = await _get_component_or_404(db, component_id)

    if name is not None:
        component.name = name
    if description is not None:
        component.description = description
    if provider_id is not None:
        component.provider_id = provider_id
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
    if gitlab_project_id is not None:
        project_svc = GitlabProjectService(db)
        project = await project_svc._get_project_or_404(gitlab_project_id)
        if project.project_type != GitlabProjectType.components:
            raise DomainError("Component must be linked to a components project", 422)
        component.gitlab_project_id = gitlab_project_id
        component.provider_id = project.provider_id
        component.project_path = project.full_path

    component.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(component)
    return component


async def delete_component(db: AsyncSession, component_id: int) -> None:
    """Delete a GitLab component."""
    component = await _get_component_or_404(db, component_id)
    await db.delete(component)
    await db.commit()


async def push_component(
    db: AsyncSession,
    component_id: int,
    user: User,
    content: str,
    file_path: str | None = None,
    commit_message: str | None = None,
    tag_name: str | None = None,
) -> GitLabComponent:
    """Push/update a component's content in its GitLab project (files + tag)."""
    from app.services.gitlab_projects._files import create_tag, upsert_file

    component = await _get_component_with_project(db, component_id)
    project_svc = GitlabProjectService(db)
    project = component.gitlab_project
    if project is None:
        raise DomainError("Component is not linked to a gitlab project", 422)
    if project.project_type != GitlabProjectType.components:
        raise DomainError("Component project must be of type 'components'", 422)
    await project_svc._ensure_can_mutate(project, user)

    target_path = file_path or f"templates/{component.component_path}"
    gl = get_provider_gitlab_client(project.provider)
    branch = project.default_branch
    commit_message = commit_message or f"Update {target_path} via BigBug"
    await upsert_file(
        gl,
        project.full_path,
        target_path,
        content,
        branch,
        commit_message,
    )

    if tag_name:
        await create_tag(gl, project.full_path, tag_name, branch, f"Release {tag_name}")
        # Store the semantic version without the leading 'v'.
        component.version = tag_name.removeprefix("v")
        component.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(component)

    return component


async def pull_component(
    db: AsyncSession,
    component_id: int,
    user: User,
) -> dict[str, Any]:
    """Return a component's current content from GitLab for UI editing."""
    from app.services.gitlab_projects._files import get_file_content

    component = await _get_component_with_project(db, component_id)
    project_svc = GitlabProjectService(db)
    project = component.gitlab_project
    if project is None:
        raise DomainError("Component is not linked to a gitlab project", 422)
    await project_svc._ensure_can_read(project, user)

    file_path = f"templates/{component.component_path}"
    ref = component.version or project.default_branch
    gl = get_provider_gitlab_client(project.provider)
    content = await get_file_content(gl, project.full_path, file_path, ref)
    if content is None:
        raise NotFoundError(f"Component file '{file_path}' not found in GitLab")
    return {"file_path": file_path, "content": content, "ref": ref}
