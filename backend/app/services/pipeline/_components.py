"""GitLab CI/CD component CRUD and input validation helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.gitlab_component import GitLabComponent

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
    provider_id: int,
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
        provider_id=provider_id,
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
    provider_id: int | None = None,
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

    component.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(component)
    return component


async def delete_component(db: AsyncSession, component_id: int) -> None:
    """Delete a GitLab component."""
    component = await _get_component_or_404(db, component_id)
    await db.delete(component)
    await db.commit()
