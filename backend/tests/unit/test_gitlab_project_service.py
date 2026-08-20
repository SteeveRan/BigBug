"""
@file test_gitlab_project_service.py
@description Unit tests for GitlabProjectService access matrix, provider usage
              accounting and component presets. No GitLab API — the GitLab
              client factory is patched where a project would be created.
@dependencies backend/app/services/gitlab_projects/_service.py,
              backend/app/services/providers/service.py,
              backend/app/services/pipeline/_components.py
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainError
from app.models.gitlab_project import GitlabProject, GitlabProjectType, ProjectVisibility
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.models.user import User
from app.schemas.gitlab_project import GitlabProjectCreate
from app.services.gitlab_projects import GitlabProjectService
from app.services.providers.service import ProviderService


def _user(user_id: int, permissions: list[str]) -> User:
    user = User(username=f"u{user_id}", email=f"u{user_id}@test.com")
    user.id = user_id
    user._cached_permissions = permissions
    return user


ADMIN = [
    "gitlab_projects:read",
    "gitlab_projects:write",
    "gitlab_projects:delete",
    "gitlab_projects:read_all",
    "components:read",
    "components:write",
    "components:delete",
    "components:push",
    "pipelines:write",
    "providers_system:write",
]

COMPONENT_DEV = [
    "gitlab_projects:read",
    "gitlab_projects:write",
    "components:read",
    "components:push",
]


async def _seed_provider(db: AsyncSession, **overrides) -> ResourceProvider:
    values = {
        "domain": ProviderDomain.git,
        "subtype": ProviderSubtype.gitlab,
        "category": ProviderCategory.system,
        "direction": ProviderDirection.internal,
        "name": "gitlab-system",
        "label": "GitLab (system)",
        "base_url": "https://gitlab.example.com",
    }
    values.update(overrides)
    if values["name"] == "gitlab-system":
        values["name"] = f"gitlab-system-{id(values):x}"
    provider = ResourceProvider(**values)
    db.add(provider)
    await db.commit()
    await db.refresh(provider)
    return provider


async def _seed_project(db: AsyncSession, provider: ResourceProvider, **overrides) -> GitlabProject:
    values = {
        "name": "components",
        "path": "components",
        "namespace_path": "bigbug-mirrors",
        "full_path": "bigbug-mirrors/components",
        "project_type": GitlabProjectType.components,
        "visibility": ProjectVisibility.owner,
        "provider_id": provider.id,
        "owner_user_id": 1,
        "default_branch": "main",
    }
    values.update(overrides)
    project = GitlabProject(**values)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


class TestPresets:
    def test_list_presets_returns_six(self):
        from app.services.pipeline._components import list_presets

        presets = list_presets()
        assert len(presets) == 6
        keys = {p["key"] for p in presets}
        assert keys == {
            "docker_hub_to_harbor",
            "gold_image",
            "app_image",
            "mirror",
            "docker_sync",
            "helm_sync",
        }

    def test_crane_preset_extracts_required_inputs(self):
        from app.services.pipeline._components import list_presets

        crane = next(p for p in list_presets() if p["key"] == "docker_hub_to_harbor")
        assert "target_registry" in crane["inputs_schema"].get("required", [])


class TestCreateProjectAccess:
    @pytest.mark.asyncio
    async def test_create_requires_write_permission(self, db_session: AsyncSession):
        provider = await _seed_provider(db_session)
        svc = GitlabProjectService(db_session)
        data = GitlabProjectCreate(
            name="components",
            path="components",
            namespace_path="bigbug-mirrors",
            project_type=GitlabProjectType.components,
            provider_id=provider.id,
        )

        with pytest.raises(DomainError) as exc_info:
            await svc.create_project(_user(2, ["components:push"]), data)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_components_project_requires_components_push(self, db_session: AsyncSession):
        provider = await _seed_provider(db_session)
        svc = GitlabProjectService(db_session)
        data = GitlabProjectCreate(
            name="components",
            path="components",
            namespace_path="bigbug-mirrors",
            project_type=GitlabProjectType.components,
            provider_id=provider.id,
        )

        # has gitlab_projects:write but not components:push → denied by type gate
        with pytest.raises(DomainError) as exc_info:
            await svc.create_project(_user(2, ["gitlab_projects:write"]), data)
        assert "components:push" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_success(self, db_session: AsyncSession):
        provider = await _seed_provider(db_session)
        svc = GitlabProjectService(db_session)
        data = GitlabProjectCreate(
            name="components",
            path="components",
            namespace_path="bigbug-mirrors",
            project_type=GitlabProjectType.components,
            provider_id=provider.id,
        )

        # Patch the namespace resolution and the GitLab client factory together;
        # projects.create is stubbed on the returned client object.
        with (
            patch.object(svc, "_resolve_namespace", new=AsyncMock(return_value=42)),
            patch(
                "app.services.gitlab_projects._service.get_provider_gitlab_client"
            ) as client_factory,
        ):
            gl = client_factory.return_value
            gl.projects.create.return_value = type(
                "GLProject",
                (),
                {"id": 101, "web_url": "https://gitlab.example.com/grp/components"},
            )()
            project = await svc.create_project(_user(1, ADMIN), data)

        assert project.full_path == "bigbug-mirrors/components"
        assert project.external_id == "101"
        assert project.owner_user_id == 1
        assert project.status_flag == 0


class TestMutateTypeGate:
    @pytest.mark.asyncio
    async def test_pipeline_project_requires_pipelines_write(self, db_session: AsyncSession):
        provider = await _seed_provider(db_session)
        project = await _seed_project(
            db_session, provider, project_type=GitlabProjectType.pipelines
        )
        svc = GitlabProjectService(db_session)

        # component dev has components:push but not pipelines:write
        with pytest.raises(DomainError) as exc_info:
            await svc._ensure_can_mutate(project, _user(2, COMPONENT_DEV))
        assert "pipelines:write" in exc_info.value.detail


class TestProviderUsage:
    @pytest.mark.asyncio
    async def test_usage_includes_gitlab_projects(self, db_session: AsyncSession):
        provider = await _seed_provider(db_session)
        await _seed_project(db_session, provider)

        usage = await ProviderService(db_session).get_usage(provider.id)

        assert {"resource": "gitlab_projects", "count": 1} in usage
