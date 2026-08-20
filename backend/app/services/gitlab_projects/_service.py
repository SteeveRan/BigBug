"""GitlabProjectService — CRUD, import, sync, files, tags and sharing for
``gitlab_projects``.

Access mirrors the ResourceProvider ownership model (owner/team/public +
``gitlab_projects:read_all``) with an additional *type permission* gate: mutating
a ``components`` project requires ``components:push``; a ``pipelines`` project
requires ``pipelines:write``. The GitLab provider is resolved per project so a
user can work against their own private GitLab, not only the platform one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import gitlab
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import DomainError
from app.models.gitlab_project import GitlabProject, GitlabProjectType, ProjectVisibility
from app.models.resource_provider import (
    ProviderCategory,
    ResourceProvider,
)
from app.models.team_member import TeamMember
from app.models.user import User
from app.services.gitlab_projects._clients import (
    _get_gitlab_provider_or_404,
    get_provider_gitlab_client,
)

# Status flags (unified convention 0-4)
STATUS_OK = 0
STATUS_FAILED = 1
STATUS_WARNING = 2
STATUS_PENDING = 4

# Type-specific permission required to mutate a project of each type (4.2).
REQUIRED_WRITE: dict[GitlabProjectType, str] = {
    GitlabProjectType.components: "components:push",
    GitlabProjectType.pipelines: "pipelines:write",
}


class GitlabProjectService:
    """Business logic for the ``gitlab_projects`` entity."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Permission helpers ──────────────────────────────────────────────

    async def _permissions_async(self, user: User) -> set[str]:
        cached = getattr(user, "_cached_permissions", [])
        if cached:
            return set(cached)
        from app.services.rbac_service import RBACService

        return set(await RBACService(self.db).get_user_permissions(user.id))

    async def _is_team_member(self, team_id: int, user_id: int) -> bool:
        result = await self.db.execute(
            select(TeamMember).where(
                TeamMember.team_id == team_id,
                TeamMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def _is_owner(self, project: GitlabProject, user: User) -> bool:
        return project.owner_user_id == user.id

    async def _can_read(self, project: GitlabProject, user: User) -> bool:
        perms = await self._permissions_async(user)
        if "gitlab_projects:read_all" in perms or project.visibility == ProjectVisibility.public:
            return True
        if await self._is_owner(project, user):
            return True
        return (
            project.visibility == ProjectVisibility.team
            and project.team_id is not None
            and await self._is_team_member(project.team_id, user.id)
        )

    async def _ensure_can_read(self, project: GitlabProject, user: User) -> None:
        if not await self._can_read(project, user):
            raise DomainError("Access denied: not the owner of this gitlab project", 403)

    async def _ensure_can_mutate(self, project: GitlabProject, user: User) -> None:
        perms = await self._permissions_async(user)
        required = REQUIRED_WRITE.get(project.project_type)
        if required and required not in perms and "gitlab_projects:read_all" not in perms:
            raise DomainError(
                f"Permission denied: '{required}' required to mutate a "
                f"{project.project_type.value} project",
                403,
            )
        await self._ensure_can_read(project, user)

    # ── Provider helpers ────────────────────────────────────────────────

    async def _get_provider_or_404(self, provider_id: int) -> ResourceProvider:
        return await _get_gitlab_provider_or_404(self.db, provider_id)

    async def _ensure_can_use_provider(self, provider: ResourceProvider, user: User) -> None:
        """Only the owner of a private provider or an admin with
        ``providers_system:write`` (for system providers) may attach projects."""
        perms = await self._permissions_async(user)
        if provider.category == ProviderCategory.system:
            if "providers_system:write" not in perms and "gitlab_projects:read_all" not in perms:
                raise DomainError(
                    "System providers require providers_system:write to attach projects",
                    403,
                )
            return
        if provider.owner_user_id == user.id:
            return
        if "gitlab_projects:read_all" in perms:
            return
        raise DomainError("Access denied: not the owner of this private provider", 403)

    # ── Fetch / list ────────────────────────────────────────────────────

    async def _get_project_or_404(self, project_id: int) -> GitlabProject:
        result = await self.db.execute(
            select(GitlabProject)
            .options(
                selectinload(GitlabProject.provider),
                selectinload(GitlabProject.owner),
                selectinload(GitlabProject.team),
            )
            .where(GitlabProject.id == project_id)
        )
        project = result.scalar_one_or_none()
        if project is None or project.is_deleted:
            raise DomainError(f"GitlabProject {project_id} not found", 404)
        return project

    async def list_projects(self, user: User) -> list[GitlabProject]:
        perms = await self._permissions_async(user)
        stmt = select(GitlabProject).where(GitlabProject.is_deleted.is_(False))
        if "gitlab_projects:read_all" not in perms:
            conditions = [
                (GitlabProject.visibility == ProjectVisibility.public),
                (GitlabProject.owner_user_id == user.id),
                (
                    (GitlabProject.visibility == ProjectVisibility.team)
                    & GitlabProject.team_id.in_(
                        select(TeamMember.team_id).where(TeamMember.user_id == user.id)
                    )
                ),
            ]
            stmt = stmt.where(or_(*conditions))
        result = await self.db.execute(
            stmt.options(selectinload(GitlabProject.provider)).order_by(GitlabProject.name)
        )
        return list(result.scalars().all())

    async def get_project(self, project_id: int, user: User) -> GitlabProject:
        project = await self._get_project_or_404(project_id)
        await self._ensure_can_read(project, user)
        return project

    # ── CRUD ────────────────────────────────────────────────────────────

    async def create_project(self, user: User, data: Any) -> GitlabProject:
        perms = await self._permissions_async(user)
        if "gitlab_projects:write" not in perms:
            raise DomainError("Permission denied: 'gitlab_projects:write' required", 403)
        required = REQUIRED_WRITE.get(data.project_type)
        if required and required not in perms:
            raise DomainError(
                f"Permission denied: '{required}' required to create a "
                f"{data.project_type.value} project",
                403,
            )

        provider = await self._get_provider_or_404(data.provider_id)
        await self._ensure_can_use_provider(provider, user)

        full_path = f"{data.namespace_path.rstrip('/')}/{data.path.lstrip('/')}"

        # duplicate full_path on this provider → 409
        existing = await self.db.execute(
            select(GitlabProject).where(
                GitlabProject.provider_id == provider.id,
                GitlabProject.full_path == full_path,
                GitlabProject.is_deleted.is_(False),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DomainError(f"Project '{full_path}' already exists on this provider", 409)

        if data.visibility == ProjectVisibility.team:
            if data.team_id is None:
                raise DomainError("team_id is required when visibility is 'team'", 422)
            if not await self._is_team_member(data.team_id, user.id):
                raise DomainError("you must be a member of the target team", 422)

        gl = get_provider_gitlab_client(provider)
        namespace_id = await self._resolve_namespace(gl, data.namespace_path, data.create_namespace)

        try:
            gl_project = gl.projects.create(
                {
                    "name": data.name,
                    "path": data.path,
                    "namespace_id": namespace_id,
                    "visibility": data.gitlab_visibility,
                    "default_branch": data.default_branch,
                    "initialize_with_readme": data.initialize_with_readme,
                    "description": data.description,
                }
            )
        except gitlab.GitlabError as exc:
            raise self._gitlab_error(exc) from exc

        project = GitlabProject(
            name=data.name,
            path=data.path,
            namespace_path=data.namespace_path.rstrip("/"),
            full_path=full_path,
            project_type=data.project_type,
            visibility=data.visibility,
            provider_id=provider.id,
            external_id=str(gl_project.id),
            web_url=getattr(gl_project, "web_url", None),
            default_branch=data.default_branch,
            gitlab_visibility=data.gitlab_visibility,
            description=data.description,
            owner_user_id=user.id,
            team_id=data.team_id if data.visibility == ProjectVisibility.team else None,
            status_flag=STATUS_OK,
            last_synced_at=datetime.now(UTC),
        )
        self.db.add(project)
        await self.db.commit()
        return await self._get_project_or_404(project.id)

    async def _resolve_namespace(
        self, gl: gitlab.Gitlab, namespace_path: str, create_namespace: bool
    ) -> int:
        """Resolve a group/personal namespace id by path. Optionally create a group."""
        try:
            groups = gl.groups.list(search=namespace_path, all=True)
            for group in groups:
                if group.full_path == namespace_path or group.path == namespace_path:
                    return group.id
        except gitlab.GitlabError as exc:
            raise self._gitlab_error(exc) from exc

        try:
            namespaces = gl.namespaces.list(search=namespace_path)
            for ns in namespaces:
                if ns.full_path == namespace_path or ns.path == namespace_path:
                    return ns.id
        except gitlab.GitlabError:
            # namespaces API may be unavailable on older instances — fall through.
            pass

        if create_namespace:
            try:
                group = gl.groups.create({"name": namespace_path, "path": namespace_path})
                return group.id
            except gitlab.GitlabError as exc:
                raise self._gitlab_error(exc) from exc

        raise DomainError(f"Namespace '{namespace_path}' not found", 404)

    async def update_project(self, project_id: int, user: User, data: Any) -> GitlabProject:
        project = await self._get_project_or_404(project_id)
        await self._ensure_can_mutate(project, user)

        if data.name is not None:
            project.name = data.name
        if data.description is not None:
            project.description = data.description
        if data.gitlab_visibility is not None:
            project.gitlab_visibility = data.gitlab_visibility
        if data.default_branch is not None:
            project.default_branch = data.default_branch

        # Visibility/team mirror the provider share rules.
        if data.visibility is not None or data.team_id is not None:
            await self._apply_visibility(project, user, data.visibility, data.team_id)

        await self.db.commit()

        # Mirror name/description/visibility into GitLab.
        provider = project.provider
        if provider is not None and (data.name or data.description or data.gitlab_visibility):
            gl = get_provider_gitlab_client(provider)
            try:
                gl_project = gl.projects.get(project.full_path)
                if data.name:
                    gl_project.name = data.name
                if data.description:
                    gl_project.description = data.description
                if data.gitlab_visibility:
                    gl_project.visibility = data.gitlab_visibility
                gl_project.save()
            except gitlab.GitlabError as exc:
                raise self._gitlab_error(exc) from exc

        return await self._get_project_or_404(project.id)

    async def _apply_visibility(
        self,
        project: GitlabProject,
        user: User,
        visibility: ProjectVisibility | None,
        team_id: int | None,
    ) -> None:
        new_visibility = visibility if visibility is not None else project.visibility
        new_team_id = team_id if team_id is not None else project.team_id
        if new_visibility == ProjectVisibility.team:
            if new_team_id is None:
                raise DomainError("team_id is required when visibility is 'team'", 422)
            if not await self._is_team_member(new_team_id, user.id):
                raise DomainError("you must be a member of the target team", 422)
            project.team_id = new_team_id
        else:
            project.team_id = None
        project.visibility = new_visibility

    async def delete_project(self, project_id: int, user: User, hard: bool) -> None:
        project = await self._get_project_or_404(project_id)
        perms = await self._permissions_async(user)
        if "gitlab_projects:delete" not in perms:
            raise DomainError("Permission denied: 'gitlab_projects:delete' required", 403)
        await self._ensure_can_read(project, user)

        # Block hard delete while live components/pipelines still reference it.
        if hard:
            from app.models.gitlab_component import GitLabComponent
            from app.models.pipeline import Pipeline

            comp_count = await self.db.execute(
                select(func.count())
                .select_from(GitLabComponent)
                .where(GitLabComponent.gitlab_project_id == project_id)
            )
            pipe_count = await self.db.execute(
                select(func.count())
                .select_from(Pipeline)
                .where(Pipeline.gitlab_project_id == project_id, ~Pipeline.is_deleted)
            )
            if (comp_count.scalar_one() or 0) > 0 or (pipe_count.scalar_one() or 0) > 0:
                raise DomainError(
                    "Cannot hard-delete a project referenced by components or pipelines",
                    409,
                )

        if hard:
            provider = project.provider
            if provider is not None:
                gl = get_provider_gitlab_client(provider)
                try:
                    gl_project = gl.projects.get(project.full_path)
                    gl_project.delete()
                except gitlab.GitlabError as exc:
                    raise self._gitlab_error(exc) from exc

        project.is_deleted = True
        project.deleted_at = datetime.now(UTC)
        await self.db.commit()

    # ── Import / sync ───────────────────────────────────────────────────

    async def import_project(
        self,
        user: User,
        provider_id: int,
        full_path: str,
        project_type: GitlabProjectType,
        visibility: ProjectVisibility,
        team_id: int | None,
    ) -> GitlabProject:
        perms = await self._permissions_async(user)
        if "gitlab_projects:write" not in perms:
            raise DomainError("Permission denied: 'gitlab_projects:write' required", 403)
        provider = await self._get_provider_or_404(provider_id)
        await self._ensure_can_use_provider(provider, user)

        gl = get_provider_gitlab_client(provider)
        try:
            gl_project = gl.projects.get(full_path)
        except gitlab.GitlabError as exc:
            raise self._gitlab_error(exc) from exc

        namespace_path, _, path = full_path.rpartition("/")
        if not namespace_path:
            namespace_path = str(getattr(gl_project, "namespace", {}).get("full_path", "")) or path

        existing = await self.db.execute(
            select(GitlabProject).where(
                GitlabProject.provider_id == provider.id,
                GitlabProject.full_path == full_path,
                GitlabProject.is_deleted.is_(False),
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DomainError(f"Project '{full_path}' already exists on this provider", 409)

        project = GitlabProject(
            name=getattr(gl_project, "name", path),
            path=path,
            namespace_path=namespace_path,
            full_path=full_path,
            project_type=project_type,
            visibility=visibility,
            provider_id=provider.id,
            external_id=str(gl_project.id),
            web_url=getattr(gl_project, "web_url", None),
            default_branch=getattr(gl_project, "default_branch", "main") or "main",
            gitlab_visibility=getattr(gl_project, "visibility", None),
            description=getattr(gl_project, "description", None),
            owner_user_id=user.id,
            team_id=team_id if visibility == ProjectVisibility.team else None,
            status_flag=STATUS_OK,
            last_synced_at=datetime.now(UTC),
        )
        self.db.add(project)
        await self.db.commit()
        return await self._get_project_or_404(project.id)

    async def sync_project(self, project_id: int, user: User) -> GitlabProject:
        project = await self._get_project_or_404(project_id)
        await self._ensure_can_read(project, user)
        provider = project.provider
        if provider is None:
            raise DomainError("Project has no provider", 404)

        gl = get_provider_gitlab_client(provider)
        try:
            gl_project = gl.projects.get(project.full_path)
        except gitlab.GitlabError as exc:
            project.status_flag = STATUS_FAILED
            project.status_text = f"GitLab sync failed: {exc}"
            await self.db.commit()
            raise self._gitlab_error(exc) from exc

        project.external_id = str(gl_project.id)
        project.web_url = getattr(gl_project, "web_url", project.web_url)
        project.default_branch = getattr(gl_project, "default_branch", project.default_branch)
        project.gitlab_visibility = getattr(gl_project, "visibility", project.gitlab_visibility)
        project.last_synced_at = datetime.now(UTC)

        if getattr(gl_project, "archived", False):
            project.status_flag = STATUS_WARNING
            project.status_text = "Project is archived in GitLab"
        else:
            project.status_flag = STATUS_OK
            project.status_text = None

        await self.db.commit()
        return await self._get_project_or_404(project.id)

    # ── Files / tags ────────────────────────────────────────────────────

    async def _project_client(
        self, project: GitlabProject
    ) -> tuple[gitlab.Gitlab, ResourceProvider]:
        provider = project.provider
        if provider is None:
            raise DomainError("Project has no provider", 404)
        return get_provider_gitlab_client(provider), provider

    async def list_files(
        self, project_id: int, user: User, ref: str, path: str | None
    ) -> list[dict]:
        from app.services.gitlab_projects._files import list_tree

        project = await self._get_project_or_404(project_id)
        await self._ensure_can_read(project, user)
        gl, _ = await self._project_client(project)
        return await list_tree(gl, project.full_path, ref, path)

    async def upsert_file(
        self,
        project_id: int,
        user: User,
        file_path: str,
        content: str,
        branch: str | None,
        commit_message: str | None,
        encoding: str,
    ) -> dict:
        from app.services.gitlab_projects._files import upsert_file

        project = await self._get_project_or_404(project_id)
        await self._ensure_can_mutate(project, user)
        gl, _ = await self._project_client(project)
        branch = branch or project.default_branch
        commit_message = commit_message or f"Update {file_path} via BigBug"
        return await upsert_file(
            gl, project.full_path, file_path, content, branch, commit_message, encoding
        )

    async def delete_file(
        self,
        project_id: int,
        user: User,
        file_path: str,
        branch: str | None,
        commit_message: str | None,
    ) -> None:
        from app.services.gitlab_projects._files import delete_file

        project = await self._get_project_or_404(project_id)
        await self._ensure_can_mutate(project, user)
        gl, _ = await self._project_client(project)
        branch = branch or project.default_branch
        commit_message = commit_message or f"Delete {file_path} via BigBug"
        await delete_file(gl, project.full_path, file_path, branch, commit_message)

    async def list_tags(self, project_id: int, user: User) -> list[dict]:
        from app.services.gitlab_projects._files import list_tags

        project = await self._get_project_or_404(project_id)
        await self._ensure_can_read(project, user)
        gl, _ = await self._project_client(project)
        return await list_tags(gl, project.full_path)

    async def create_tag(
        self, project_id: int, user: User, tag_name: str, ref: str | None, message: str | None
    ) -> dict:
        from app.services.gitlab_projects._files import create_tag

        project = await self._get_project_or_404(project_id)
        await self._ensure_can_mutate(project, user)
        gl, _ = await self._project_client(project)
        return await create_tag(gl, project.full_path, tag_name, ref, message)

    # ── Share / unshare ─────────────────────────────────────────────────

    async def share_project(self, project_id: int, team_id: int, user: User) -> GitlabProject:
        project = await self._get_project_or_404(project_id)
        await self._ensure_can_read(project, user)
        if not await self._is_owner(
            project, user
        ) and "gitlab_projects:read_all" not in await self._permissions_async(user):
            raise DomainError("Access denied: not the owner of this gitlab project", 403)
        if project.visibility == ProjectVisibility.team:
            raise DomainError("Project is already shared with a team", 409)
        if not await self._is_team_member(team_id, user.id):
            raise DomainError("you must be a member of the target team", 422)
        project.visibility = ProjectVisibility.team
        project.team_id = team_id
        await self.db.commit()
        return await self._get_project_or_404(project.id)

    async def unshare_project(self, project_id: int, user: User) -> GitlabProject:
        project = await self._get_project_or_404(project_id)
        await self._ensure_can_read(project, user)
        if not await self._is_owner(
            project, user
        ) and "gitlab_projects:read_all" not in await self._permissions_async(user):
            raise DomainError("Access denied: not the owner of this gitlab project", 403)
        if project.visibility != ProjectVisibility.team:
            raise DomainError("Project is not shared with a team", 409)
        project.visibility = ProjectVisibility.owner
        project.team_id = None
        await self.db.commit()
        return await self._get_project_or_404(project.id)

    # ── Error mapping ───────────────────────────────────────────────────

    @staticmethod
    def _gitlab_error(exc: gitlab.GitlabError) -> DomainError:
        code = getattr(exc, "response_code", None)
        if code == 401:
            return DomainError(
                "GitLab authentication failed (HTTP 401). Check the provider credential.", 401
            )
        if code == 403:
            return DomainError(
                "GitLab access forbidden (HTTP 403). The credential lacks permission.", 403
            )
        if code == 404:
            return DomainError("GitLab resource not found (HTTP 404).", 404)
        if code == 409:
            return DomainError(f"GitLab conflict (HTTP 409): {exc}", 409)
        return DomainError(f"GitLab request failed: {exc}", 502)
