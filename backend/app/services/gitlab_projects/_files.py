"""GitLab repository file/tag operations shared by project, component and
pipeline services.

All functions take an already-built ``gitlab.Gitlab`` client and a project
reference (numeric id or URL-encoded full path) so they can be reused without
coupling to the ORM. GitLab API failures are mapped to :class:`DomainError`
so callers can propagate a meaningful HTTP status.
"""

from __future__ import annotations

import base64
from typing import Any

import gitlab

from app.core.exceptions import DomainError


def _gitlab_error(exc: gitlab.GitlabError) -> DomainError:
    """Map a python-gitlab failure to a domain error with a useful status."""
    code = getattr(exc, "response_code", None)
    if code == 401:
        return DomainError(
            "GitLab authentication failed (HTTP 401). Check the provider credential.",
            401,
        )
    if code == 403:
        return DomainError(
            "GitLab access forbidden (HTTP 403). The credential lacks permission.",
            403,
        )
    if code == 404:
        return DomainError("GitLab resource not found (HTTP 404).", 404)
    if code == 409:
        return DomainError(f"GitLab conflict (HTTP 409): {exc}", 409)
    return DomainError(f"GitLab request failed: {exc}", 502)


async def _get_project(gl: gitlab.Gitlab, project_ref: str | int) -> Any:
    """Resolve a GitLab project by numeric id or full path."""
    try:
        return gl.projects.get(project_ref)
    except gitlab.GitlabError as exc:
        raise _gitlab_error(exc) from exc


async def list_tree(
    gl: gitlab.Gitlab,
    project_ref: str | int,
    ref: str,
    path: str | None,
) -> list[dict[str, Any]]:
    """Return the repository tree (files/dirs) at *ref* and optional *path*."""
    project = await _get_project(gl, project_ref)
    try:
        items = project.repository_tree(ref=ref, path=path, recursive=False, per_page=100)
    except gitlab.GitlabError as exc:
        raise _gitlab_error(exc) from exc
    return [
        {
            "path": item.get("path"),
            "type": item.get("type"),
            "name": item.get("name"),
        }
        for item in items
    ]


async def get_file_content(
    gl: gitlab.Gitlab,
    project_ref: str | int,
    file_path: str,
    ref: str,
) -> str | None:
    """Return decoded file content, or ``None`` when the file does not exist."""
    project = await _get_project(gl, project_ref)
    try:
        f = project.files.get(file_path, ref=ref)
    except gitlab.GitlabError as exc:
        if getattr(exc, "response_code", None) == 404:
            return None
        raise _gitlab_error(exc) from exc
    content = f.decode()
    if isinstance(content, bytes):
        content = base64.b64encode(content).decode() if f.encoding == "base64" else content.decode()
    return content


async def upsert_file(
    gl: gitlab.Gitlab,
    project_ref: str | int,
    file_path: str,
    content: str,
    branch: str,
    commit_message: str,
    encoding: str = "text",
) -> dict[str, Any]:
    """Idempotent create-or-update of a repository file by content.

    When the file already exists with identical content no commit is issued
    (the "same content → no second commit" rule from the old provisioning
    script).
    """
    project = await _get_project(gl, project_ref)
    payload = {
        "file_path": file_path,
        "branch": branch,
        "content": content,
        "commit_message": commit_message,
        "encoding": encoding,
    }

    existing = await get_file_content(gl, project_ref, file_path, branch)
    if existing is not None:
        if existing == content:
            return {"action": "noop", "file_path": file_path}
        try:
            f = project.files.get(file_path, ref=branch)
            f.content = content
            f.encoding = encoding
            f.save(branch=branch, commit_message=commit_message)
            return {"action": "updated", "file_path": file_path}
        except gitlab.GitlabError as exc:
            raise _gitlab_error(exc) from exc

    try:
        project.files.create(payload)
        return {"action": "created", "file_path": file_path}
    except gitlab.GitlabError as exc:
        raise _gitlab_error(exc) from exc


async def delete_file(
    gl: gitlab.Gitlab,
    project_ref: str | int,
    file_path: str,
    branch: str,
    commit_message: str,
) -> None:
    """Delete a repository file via the Files API (commit)."""
    project = await _get_project(gl, project_ref)
    try:
        project.files.delete(file_path, branch=branch, commit_message=commit_message)
    except gitlab.GitlabError as exc:
        raise _gitlab_error(exc) from exc


async def list_tags(gl: gitlab.Gitlab, project_ref: str | int) -> list[dict[str, Any]]:
    """Return the project's GitLab tags (name, target, message, created_at)."""
    project = await _get_project(gl, project_ref)
    try:
        tags = project.tags.list(all=True)
    except gitlab.GitlabError as exc:
        raise _gitlab_error(exc) from exc
    return [
        {
            "name": t.name,
            "target": getattr(t, "target", None),
            "message": getattr(t, "message", None),
            "created_at": getattr(t, "created_at", None),
        }
        for t in tags
    ]


async def create_tag(
    gl: gitlab.Gitlab,
    project_ref: str | int,
    tag_name: str,
    ref: str | None,
    message: str | None,
) -> dict[str, Any]:
    """Create a GitLab tag. Re-creating an existing tag raises 409."""
    project = await _get_project(gl, project_ref)
    data: dict[str, Any] = {"tag_name": tag_name, "ref": ref or project.default_branch}
    if message:
        data["message"] = message
    try:
        tag = project.tags.create(data)
    except gitlab.GitlabError as exc:
        raise _gitlab_error(exc) from exc
    return {
        "name": tag.name,
        "target": getattr(tag, "target", None),
        "message": getattr(tag, "message", None),
    }
