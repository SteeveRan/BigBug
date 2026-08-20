"""
@file test_pipeline_service.py
@description Unit tests for Pipeline service functions — get_pipeline_runs,
             trigger_pipeline, update_pipeline_status, list_components,
             create_component, update_component, delete_component.
@dependencies pytest, pytest-asyncio, backend/tests/conftest.py
@relatedFiles ../../app/services/pipeline.py, ../../app/models/pipeline_run.py,
               ../../app/models/gitlab_component.py
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, DomainError, NotFoundError
from app.models.gitlab_component import GitLabComponent
from app.models.pipeline import Pipeline
from app.models.pipeline_run import PipelineRun
from app.models.resource_provider import ResourceProvider
from app.models.sync_group import SyncGroup
from app.schemas.pipeline import PipelineCreate, PipelineUpdate
from app.services import pipeline as pipeline_service

# ──────────────────────────────────────────────────────────────────────
# get_pipeline_runs
# ──────────────────────────────────────────────────────────────────────


class TestGetPipelineRuns:
    """Tests for get_pipeline_runs()"""

    async def _seed_runs(self, db_session: AsyncSession) -> list[PipelineRun]:
        """Create 4 pipeline runs with varying statuses."""
        runs = [
            PipelineRun(
                provider_id=1,
                gitlab_project_id=100 + i,
                ref="main",
                status_flag=flag,
                status_text=text,
            )
            for i, (flag, text) in enumerate(
                [(0, "OK"), (1, "Failed"), (3, "Running"), (4, "Pending")]
            )
        ]
        db_session.add_all(runs)
        await db_session.commit()
        return runs

    @pytest.mark.asyncio
    async def test_get_runs_returns_list(self, db_session: AsyncSession):
        """get_pipeline_runs returns list of runs."""
        await self._seed_runs(db_session)
        items, total = await pipeline_service.get_pipeline_runs(db_session)
        assert total == 4
        assert len(items) == 4
        assert all(isinstance(r, PipelineRun) for r in items)

    @pytest.mark.asyncio
    async def test_get_runs_filter_by_status(self, db_session: AsyncSession):
        """get_pipeline_runs filters by status_flag."""
        await self._seed_runs(db_session)
        items, total = await pipeline_service.get_pipeline_runs(db_session, status_filter=0)
        assert total == 1
        assert items[0].status_flag == 0

    @pytest.mark.asyncio
    async def test_get_runs_pagination(self, db_session: AsyncSession):
        """get_pipeline_runs respects pagination."""
        await self._seed_runs(db_session)
        items, total = await pipeline_service.get_pipeline_runs(db_session, page=1, page_size=2)
        assert total == 4
        assert len(items) == 2

        items_page2, _ = await pipeline_service.get_pipeline_runs(db_session, page=2, page_size=2)
        assert len(items_page2) == 2

    @pytest.mark.asyncio
    async def test_get_runs_empty(self, db_session: AsyncSession):
        """get_pipeline_runs returns empty when no runs exist."""
        items, total = await pipeline_service.get_pipeline_runs(db_session)
        assert total == 0
        assert items == []


# ──────────────────────────────────────────────────────────────────────
# get_pipeline_run
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_pipeline_run_not_found(db_session: AsyncSession):
    """get_pipeline_run raises NotFoundError for nonexistent run."""
    with pytest.raises(NotFoundError) as exc_info:
        await pipeline_service.get_pipeline_run(db_session, 99999)
    assert "id=99999" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_pipeline_run_found(db_session: AsyncSession):
    """get_pipeline_run returns run when it exists."""
    run = PipelineRun(
        provider_id=1,
        gitlab_project_id=42,
        ref="main",
    )
    db_session.add(run)
    await db_session.commit()

    fetched = await pipeline_service.get_pipeline_run(db_session, run.id)
    assert fetched.id == run.id
    assert fetched.gitlab_project_id == 42
    assert fetched.ref == "main"


# ──────────────────────────────────────────────────────────────────────
# trigger_pipeline
# ──────────────────────────────────────────────────────────────────────


class TestTriggerPipeline:
    """Tests for trigger_pipeline()"""

    @pytest.mark.asyncio
    async def test_trigger_requires_provider(self, db_session: AsyncSession):
        """trigger_pipeline raises NotFoundError when provider doesn't exist."""
        with pytest.raises(NotFoundError) as exc_info:
            await pipeline_service.trigger_pipeline(
                db_session,
                gitlab_project_id=1,
                ref="main",
                provider_id=99999,
            )
        assert "provider" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_trigger_handles_gitlab_error(self, db_session: AsyncSession):
        """trigger_pipeline records failed run on GitLab API error."""
        provider = await _seed_resource_provider(db_session)

        with patch(
            "app.services.pipeline._runs._get_provider_gitlab_client"
        ) as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            import gitlab

            mock_project.pipelines.create.side_effect = gitlab.GitlabError("Connection refused")
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_pipeline(
                db_session,
                gitlab_project_id=42,
                ref="main",
                provider_id=provider.id,
            )

        assert run.status_flag == 1  # FAILED
        assert "GitLab API error" in run.status_text

    @pytest.mark.asyncio
    async def test_trigger_creates_run_record(self, db_session: AsyncSession):
        """trigger_pipeline creates PipelineRun on success."""
        provider = await _seed_resource_provider(db_session)

        with patch(
            "app.services.pipeline._runs._get_provider_gitlab_client"
        ) as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_pipeline = MagicMock()
            mock_pipeline.id = 12345
            mock_pipeline.web_url = "https://gitlab.example.com/pipelines/12345"
            mock_project.pipelines.create.return_value = mock_pipeline
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_pipeline(
                db_session,
                gitlab_project_id=42,
                ref="main",
                variables={"KEY": "VALUE"},
                user_id=1,
                provider_id=provider.id,
            )

        assert run.status_flag == 3  # IN_PROGRESS
        assert run.gitlab_pipeline_id == 12345
        assert run.variables == {"KEY": "VALUE"}
        assert run.triggered_by_user_id == 1
        assert run.web_url == "https://gitlab.example.com/pipelines/12345"
        assert run.provider_id == provider.id


# ──────────────────────────────────────────────────────────────────────
# update_pipeline_status
# ──────────────────────────────────────────────────────────────────────


class TestUpdatePipelineStatus:
    """Tests for update_pipeline_status()"""

    @pytest.mark.asyncio
    async def test_update_status_changes_flag(self, db_session: AsyncSession):
        """update_pipeline_status updates status_flag and status_text."""
        run = PipelineRun(
            provider_id=1,
            gitlab_project_id=42,
            gitlab_pipeline_id=999,
            ref="main",
            status_flag=3,
            status_text="Running",
        )
        db_session.add(run)
        await db_session.commit()

        updated = await pipeline_service.update_pipeline_status(
            db_session,
            gitlab_pipeline_id=999,
            status="success",
            duration=120,
        )

        assert updated is not None
        assert updated.status_flag == 0  # OK (success→0)
        assert updated.status_text == "Success"
        assert updated.duration == 120
        assert updated.finished_at is not None

    @pytest.mark.asyncio
    async def test_update_status_nonexistent_run(self, db_session: AsyncSession):
        """update_pipeline_status returns None for nonexistent pipeline ID."""
        result = await pipeline_service.update_pipeline_status(
            db_session,
            gitlab_pipeline_id=99999,
            status="success",
        )
        assert result is None


# ──────────────────────────────────────────────────────────────────────
# GitLab Components
# ──────────────────────────────────────────────────────────────────────


class TestGitLabComponents:
    """Tests for component CRUD operations."""

    @pytest.mark.asyncio
    async def test_list_components_empty(self, db_session: AsyncSession):
        """list_components returns empty list when no components."""
        result = await pipeline_service.list_components(db_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_create_and_list_component(self, db_session: AsyncSession):
        """create_component and list_components work together."""
        comp = await pipeline_service.create_component(
            db_session,
            name="my-component",
            provider_id=1,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
            description="Test component",
        )

        assert comp.id is not None
        assert comp.name == "my-component"
        assert comp.is_enabled is True

        result = await pipeline_service.list_components(db_session)
        assert len(result) == 1
        assert result[0].name == "my-component"

    @pytest.mark.asyncio
    async def test_get_component_not_found(self, db_session: AsyncSession):
        """get_component raises NotFoundError for nonexistent component."""
        with pytest.raises(NotFoundError):
            await pipeline_service.get_component(db_session, 99999)

    @pytest.mark.asyncio
    async def test_update_component(self, db_session: AsyncSession):
        """update_component modifies fields correctly."""
        comp = await pipeline_service.create_component(
            db_session,
            name="old-name",
            provider_id=1,
            project_path="group/project",
            component_path=".gitlab/components/old.yml",
        )

        updated = await pipeline_service.update_component(
            db_session,
            comp.id,
            name="new-name",
            is_enabled=False,
        )

        assert updated.name == "new-name"
        assert updated.is_enabled is False
        # Unchanged fields preserved
        assert updated.project_path == "group/project"

    @pytest.mark.asyncio
    async def test_delete_component(self, db_session: AsyncSession):
        """delete_component removes the component."""
        comp = await pipeline_service.create_component(
            db_session,
            name="to-delete",
            provider_id=1,
            project_path="group/project",
            component_path=".gitlab/components/del.yml",
        )

        await pipeline_service.delete_component(db_session, comp.id)

        with pytest.raises(NotFoundError):
            await pipeline_service.get_component(db_session, comp.id)


# ──────────────────────────────────────────────────────────────────────
# Pipeline Config CRUD (git-mirroring v2)
# ──────────────────────────────────────────────────────────────────────


class TestPipelineConfigCRUD:
    """Tests for Pipeline config CRUD operations."""

    @pytest.fixture(autouse=True)
    async def _seed_component(self, db_session: AsyncSession) -> None:
        """Seed a GitLab component that PipelineComponent refs can point to."""
        result = await db_session.execute(
            select(GitLabComponent).where(GitLabComponent.name == "test-component")
        )
        if result.scalar_one_or_none() is not None:
            return
        comp = GitLabComponent(
            name="test-component",
            provider_id=1,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
        )
        db_session.add(comp)
        await db_session.commit()

    # ── create_pipeline ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_pipeline_success(self, db_session: AsyncSession):
        """Create a Pipeline with components — verify all fields."""
        comp = (
            await db_session.execute(
                select(GitLabComponent).where(GitLabComponent.name == "test-component")
            )
        ).scalar_one()

        data = PipelineCreate(
            name="my-pipeline",
            description="A test pipeline",
            ref="main",
            components=[{"component_id": comp.id, "order": 1, "overrides": {"k": "v"}}],
        )
        pipeline = await pipeline_service.create_pipeline(db_session, data)

        assert pipeline.id is not None
        assert pipeline.name == "my-pipeline"
        assert pipeline.description == "A test pipeline"
        assert pipeline.is_enabled is True
        assert pipeline.is_default is False
        assert len(pipeline.components) == 1
        assert pipeline.components[0].component_id == comp.id

    @pytest.mark.asyncio
    async def test_create_pipeline_duplicate_name(self, db_session: AsyncSession):
        """Creating a pipeline with duplicate name raises DomainError(409)."""
        data = PipelineCreate(name="unique-name")
        await pipeline_service.create_pipeline(db_session, data)

        with pytest.raises(DomainError) as exc_info:
            await pipeline_service.create_pipeline(db_session, PipelineCreate(name="unique-name"))
        assert exc_info.value.status_code == 409
        assert "Name already in use" in str(exc_info.value)

    # ── get_pipeline_configs ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_pipeline_configs_empty(self, db_session: AsyncSession):
        """get_pipeline_configs returns empty list when no configs."""
        configs = await pipeline_service.get_pipeline_configs(db_session)
        assert configs == []

    @pytest.mark.asyncio
    async def test_get_pipeline_configs_with_items(self, db_session: AsyncSession):
        """get_pipeline_configs returns created pipelines."""
        await pipeline_service.create_pipeline(db_session, PipelineCreate(name="cfg-a"))
        await pipeline_service.create_pipeline(db_session, PipelineCreate(name="cfg-b"))

        configs = await pipeline_service.get_pipeline_configs(db_session)
        assert len(configs) == 2
        names = {c.name for c in configs}
        assert names == {"cfg-a", "cfg-b"}

    @pytest.mark.asyncio
    async def test_get_pipeline_configs_filter_enabled(self, db_session: AsyncSession):
        """Filter by is_enabled."""
        await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="enabled-cfg", is_enabled=True)
        )
        await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="disabled-cfg", is_enabled=False)
        )

        configs = await pipeline_service.get_pipeline_configs(db_session, is_enabled=True)
        assert len(configs) == 1
        assert configs[0].name == "enabled-cfg"

    @pytest.mark.asyncio
    async def test_get_pipeline_configs_search(self, db_session: AsyncSession):
        """Search by name substring."""
        await pipeline_service.create_pipeline(db_session, PipelineCreate(name="alpha-config"))
        await pipeline_service.create_pipeline(db_session, PipelineCreate(name="beta-pipe"))
        await pipeline_service.create_pipeline(db_session, PipelineCreate(name="alpha-gamma"))

        configs = await pipeline_service.get_pipeline_configs(db_session, search="alpha")
        assert len(configs) == 2

    # ── get_pipeline_config ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_pipeline_config_by_id_found(self, db_session: AsyncSession):
        """get_pipeline_config returns pipeline with eager-loaded relations."""
        comp = (
            await db_session.execute(
                select(GitLabComponent).where(GitLabComponent.name == "test-component")
            )
        ).scalar_one()

        data = PipelineCreate(
            name="detail-pipe",
            components=[{"component_id": comp.id, "order": 1}],
        )
        created = await pipeline_service.create_pipeline(db_session, data)

        fetched = await pipeline_service.get_pipeline_config(db_session, created.id)
        assert fetched is not None
        assert fetched.name == "detail-pipe"
        assert len(fetched.components) == 1
        assert fetched.components[0].component is not None

    @pytest.mark.asyncio
    async def test_get_pipeline_config_by_id_not_found(self, db_session: AsyncSession):
        """Returns None for nonexistent ID."""
        result = await pipeline_service.get_pipeline_config(db_session, 99999)
        assert result is None

    # ── update_pipeline ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_update_pipeline_fields(self, db_session: AsyncSession):
        """Update scalar fields of a pipeline."""
        created = await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="update-me", description="old")
        )

        updated = await pipeline_service.update_pipeline(
            db_session, created.id, PipelineUpdate(description="new", is_enabled=False)
        )

        assert updated.description == "new"
        assert updated.is_enabled is False
        assert updated.name == "update-me"  # unchanged

    @pytest.mark.asyncio
    async def test_update_pipeline_components(self, db_session: AsyncSession):
        """Replace components on update."""
        comp = (
            await db_session.execute(
                select(GitLabComponent).where(GitLabComponent.name == "test-component")
            )
        ).scalar_one()

        created = await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="comp-pipe")
        )

        updated = await pipeline_service.update_pipeline(
            db_session,
            created.id,
            PipelineUpdate(components=[{"component_id": comp.id, "order": 1}]),
        )

        assert len(updated.components) == 1
        assert updated.components[0].component_id == comp.id

        # Replace with different set
        updated2 = await pipeline_service.update_pipeline(
            db_session,
            created.id,
            PipelineUpdate(components=[]),
        )
        assert len(updated2.components) == 0

    @pytest.mark.asyncio
    async def test_update_pipeline_default_swap(self, db_session: AsyncSession):
        """Setting is_default=True swaps the default flag from old default."""
        # Create two pipelines, make first default
        p1 = await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="first-default", is_default=True)
        )
        p2 = await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="second-not-default")
        )

        assert p1.is_default is True
        assert p2.is_default is False

        # Make second default
        updated = await pipeline_service.update_pipeline(
            db_session, p2.id, PipelineUpdate(is_default=True)
        )
        assert updated.is_default is True

        # Verify first is no longer default
        p1_after = await pipeline_service.get_pipeline_config(db_session, p1.id)
        assert p1_after.is_default is False

    # ── delete_pipeline ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_delete_pipeline_not_default(self, db_session: AsyncSession):
        """Successfully delete a non-default pipeline."""
        created = await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="deletable")
        )
        pipeline_id = created.id

        await pipeline_service.delete_pipeline(db_session, pipeline_id)

        result = await pipeline_service.get_pipeline_config(db_session, pipeline_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_default_pipeline_fails(self, db_session: AsyncSession):
        """Cannot delete the default pipeline."""
        created = await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="my-default", is_default=True)
        )

        with pytest.raises(DomainError) as exc_info:
            await pipeline_service.delete_pipeline(db_session, created.id)
        assert exc_info.value.status_code == 409
        assert "Cannot delete default" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_pipeline_in_use_fails(self, db_session: AsyncSession):
        """Cannot delete pipeline referenced by a SyncGroup."""
        created = await pipeline_service.create_pipeline(db_session, PipelineCreate(name="in-use"))

        sg = SyncGroup(name="test-sg", pipeline_id=created.id)
        db_session.add(sg)
        await db_session.commit()

        with pytest.raises(DomainError) as exc_info:
            await pipeline_service.delete_pipeline(db_session, created.id)
        assert exc_info.value.status_code == 409
        assert "in use by sync groups" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_delete_pipeline_nonexistent(self, db_session: AsyncSession):
        """Deleting nonexistent pipeline raises DomainError(404)."""
        with pytest.raises(DomainError) as exc_info:
            await pipeline_service.delete_pipeline(db_session, 99999)
        assert exc_info.value.status_code == 404

    # ── duplicate_pipeline ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_duplicate_pipeline(self, db_session: AsyncSession):
        """Duplicate copies name, is_enabled, components — forces is_default=False."""
        comp = (
            await db_session.execute(
                select(GitLabComponent).where(GitLabComponent.name == "test-component")
            )
        ).scalar_one()

        original = await pipeline_service.create_pipeline(
            db_session,
            PipelineCreate(
                name="original",
                description="Original desc",
                is_enabled=False,
                is_default=True,
                components=[{"component_id": comp.id, "order": 1}],
            ),
        )

        duplicate = await pipeline_service.duplicate_pipeline(db_session, original.id, "duplicated")

        assert duplicate.name == "duplicated"
        assert duplicate.description == "Original desc"
        assert duplicate.is_enabled is False  # inherited
        assert duplicate.is_default is False  # forced
        assert len(duplicate.components) == 1
        assert duplicate.components[0].component_id == comp.id

    @pytest.mark.asyncio
    async def test_duplicate_pipeline_name_conflict(self, db_session: AsyncSession):
        """Duplicate with existing name raises DomainError(409)."""
        existing = await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="existing-name")
        )

        with pytest.raises(DomainError) as exc_info:
            await pipeline_service.duplicate_pipeline(db_session, existing.id, "existing-name")
        assert exc_info.value.status_code == 409

    # ── get_default_pipeline ─────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_default_pipeline_returns_default(self, db_session: AsyncSession):
        """Returns the pipeline with is_default=True."""
        await pipeline_service.create_pipeline(db_session, PipelineCreate(name="non-default"))
        await pipeline_service.create_pipeline(
            db_session, PipelineCreate(name="the-default", is_default=True)
        )

        result = await pipeline_service.get_default_pipeline(db_session)
        assert result is not None
        assert result.name == "the-default"

    @pytest.mark.asyncio
    async def test_get_default_pipeline_returns_none(self, db_session: AsyncSession):
        """Returns None when no default pipeline exists."""
        await pipeline_service.create_pipeline(db_session, PipelineCreate(name="only-one"))
        result = await pipeline_service.get_default_pipeline(db_session)
        assert result is None


# ──────────────────────────────────────────────────────────────────────
# trigger_pipeline_from_config
# ──────────────────────────────────────────────────────────────────────


class TestTriggerPipelineFromConfig:
    """Tests for trigger_pipeline_from_config()"""

    async def _seed_pipeline_with_provider(self, db_session: AsyncSession, **kwargs) -> Pipeline:
        """Create a Pipeline linked to a system/internal gitlab ResourceProvider,
        reload with provider eager-loaded, and return it."""
        provider = await _seed_resource_provider(
            db_session,
            name=kwargs.pop("provider_name", "trigger-cfg-gitlab"),
        )

        pipeline = Pipeline(
            name=kwargs.pop("name", "trigger-cfg-pipeline"),
            provider_id=provider.id,
            ref=kwargs.pop("ref", "main"),
            default_variables=kwargs.pop("default_variables", {}),
            is_enabled=kwargs.pop("is_enabled", True),
            **kwargs,
        )
        db_session.add(pipeline)
        await db_session.commit()

        # Reload with provider/credential eager-loaded
        return await pipeline_service.get_pipeline_config(db_session, pipeline.id)

    @pytest.mark.asyncio
    async def test_trigger_from_config_success(self, db_session: AsyncSession):
        """Successful trigger creates PipelineRun with RUNNING status."""
        pipeline = await self._seed_pipeline_with_provider(
            db_session,
            default_variables={"SOURCE": "default-src"},
        )

        with patch(
            "app.services.pipeline._runs._get_provider_gitlab_client"
        ) as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_gl_pipeline = MagicMock()
            mock_gl_pipeline.id = 999
            mock_gl_pipeline.web_url = "https://gitlab.example.com/pipelines/999"
            mock_project.pipelines.create.return_value = mock_gl_pipeline
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_pipeline_from_config(
                db_session,
                pipeline=pipeline,
                gitlab_project_id=42,
                mirror_variables={"MIRROR": "val"},
                user_id=1,
            )

        assert run is not None
        assert run.status_flag == 3  # STATUS_IN_PROGRESS
        assert run.status_text == "Running"
        assert run.gitlab_pipeline_id == 999
        assert run.gitlab_project_id == 42
        assert run.pipeline_id == pipeline.id
        assert run.triggered_by_user_id == 1
        assert run.web_url == "https://gitlab.example.com/pipelines/999"
        assert run.started_at is not None
        # Variables: defaults merged with mirror
        assert run.variables == {"SOURCE": "default-src", "MIRROR": "val"}

    @pytest.mark.asyncio
    async def test_trigger_from_config_merges_variables(self, db_session: AsyncSession):
        """mirror_variables override default_variables with the same key."""
        pipeline = await self._seed_pipeline_with_provider(
            db_session,
            default_variables={"KEY1": "default", "KEY2": "default2"},
        )

        with patch(
            "app.services.pipeline._runs._get_provider_gitlab_client"
        ) as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_gl_pipeline = MagicMock()
            mock_gl_pipeline.id = 1
            mock_gl_pipeline.web_url = "https://gitlab.example.com/pipelines/1"
            mock_project.pipelines.create.return_value = mock_gl_pipeline
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_pipeline_from_config(
                db_session,
                pipeline=pipeline,
                gitlab_project_id=1,
                mirror_variables={"KEY1": "overridden", "KEY3": "extra"},
            )

        # KEY1 overridden, KEY2 preserved, KEY3 added
        assert run.variables == {"KEY1": "overridden", "KEY2": "default2", "KEY3": "extra"}

    @pytest.mark.asyncio
    async def test_trigger_from_config_disabled_pipeline(self, db_session: AsyncSession):
        """Disabled pipeline raises BadRequestError."""
        pipeline = await self._seed_pipeline_with_provider(
            db_session, is_enabled=False, name="disabled-pipe"
        )

        with pytest.raises(BadRequestError) as exc_info:
            await pipeline_service.trigger_pipeline_from_config(
                db_session,
                pipeline=pipeline,
                gitlab_project_id=1,
            )
        assert "disabled" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_trigger_from_config_no_provider(self, db_session: AsyncSession):
        """Pipeline without a provider raises NotFoundError."""
        pipeline = Pipeline(
            name="no-instance-pipe",
            provider_id=None,
            ref="main",
            default_variables={},
            is_enabled=True,
        )

        with pytest.raises(NotFoundError) as exc_info:
            await pipeline_service.trigger_pipeline_from_config(
                db_session,
                pipeline=pipeline,
                gitlab_project_id=1,
            )
        # Phase 4: the error mentions the provider (no provider assigned)
        assert "provider" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_trigger_from_config_gitlab_api_error(self, db_session: AsyncSession):
        """GitLab API error records a FAILED PipelineRun."""
        pipeline = await self._seed_pipeline_with_provider(
            db_session,
            default_variables={"VAR": "val"},
        )

        with patch(
            "app.services.pipeline._runs._get_provider_gitlab_client"
        ) as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            import gitlab

            mock_project.pipelines.create.side_effect = gitlab.GitlabError("Connection refused")
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_pipeline_from_config(
                db_session,
                pipeline=pipeline,
                gitlab_project_id=42,
            )

        assert run.status_flag == 1  # STATUS_FAILED
        assert "GitLab API error" in run.status_text
        assert run.pipeline_id == pipeline.id
        assert run.gitlab_project_id == 42
        assert run.variables == {"VAR": "val"}


# ──────────────────────────────────────────────────────────────────────
# monitor_pipeline_status
# ──────────────────────────────────────────────────────────────────────


class TestMonitorPipelineStatus:
    """Tests for monitor_pipeline_status()"""

    async def _seed_pipeline_run(self, db_session: AsyncSession, **kwargs) -> PipelineRun:
        """Create a PipelineRun linked to a system/internal gitlab ResourceProvider."""
        provider = await _seed_resource_provider(
            db_session,
            name=kwargs.pop("provider_name", "monitor-gitlab"),
        )

        run = PipelineRun(
            provider_id=provider.id,
            gitlab_project_id=kwargs.pop("gitlab_project_id", 42),
            gitlab_pipeline_id=kwargs.pop("gitlab_pipeline_id", 555),
            ref=kwargs.pop("ref", "main"),
            status_flag=kwargs.pop("status_flag", 3),  # RUNNING
            status_text=kwargs.pop("status_text", "Running"),
            **kwargs,
        )
        db_session.add(run)
        await db_session.commit()
        await db_session.refresh(run)
        return run

    @pytest.mark.asyncio
    async def test_monitor_nonexistent_run(self, db_session: AsyncSession):
        """monitor_pipeline_status raises NotFoundError for nonexistent run."""
        with pytest.raises(NotFoundError) as exc_info:
            await pipeline_service.monitor_pipeline_status(db_session, 99999)
        assert "id=99999" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_monitor_no_gitlab_pipeline_id(self, db_session: AsyncSession):
        """Raises BadRequestError if PipelineRun has no gitlab_pipeline_id."""
        run = await self._seed_pipeline_run(db_session, gitlab_pipeline_id=None)

        with pytest.raises(BadRequestError) as exc_info:
            await pipeline_service.monitor_pipeline_status(db_session, run.id)
        assert "gitlab_pipeline_id" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_monitor_updates_status_to_success(self, db_session: AsyncSession):
        """Polling a successful pipeline updates status to OK."""
        run = await self._seed_pipeline_run(db_session)

        with patch(
            "app.services.pipeline._clients._get_provider_gitlab_client"
        ) as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_gl_pipeline = MagicMock()
            mock_gl_pipeline.status = "success"
            mock_gl_pipeline.web_url = "https://gitlab.example.com/pipelines/555"
            mock_gl_pipeline.duration = 120
            mock_project.pipelines.get.return_value = mock_gl_pipeline
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            updated = await pipeline_service.monitor_pipeline_status(db_session, run.id)

        assert updated.status_flag == 0  # STATUS_OK
        assert updated.status_text == "Success"
        assert updated.duration == 120
        assert updated.web_url == "https://gitlab.example.com/pipelines/555"
        assert updated.finished_at is not None

    @pytest.mark.asyncio
    async def test_monitor_updates_status_to_failed(self, db_session: AsyncSession):
        """Polling a failed pipeline updates status to FAILED."""
        run = await self._seed_pipeline_run(db_session)

        with patch(
            "app.services.pipeline._clients._get_provider_gitlab_client"
        ) as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_gl_pipeline = MagicMock()
            mock_gl_pipeline.status = "failed"
            mock_gl_pipeline.duration = None
            mock_gl_pipeline.web_url = None
            mock_project.pipelines.get.return_value = mock_gl_pipeline
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            updated = await pipeline_service.monitor_pipeline_status(db_session, run.id)

        assert updated.status_flag == 1  # STATUS_FAILED
        assert updated.status_text == "Failed"

    @pytest.mark.asyncio
    async def test_monitor_handles_gitlab_error(self, db_session: AsyncSession):
        """GitLab API error sets status to WARNING."""
        run = await self._seed_pipeline_run(db_session)

        with patch(
            "app.services.pipeline._clients._get_provider_gitlab_client"
        ) as mock_client_factory:
            mock_gl = MagicMock()
            import gitlab

            mock_gl.projects.get.side_effect = gitlab.GitlabError("Timeout")
            mock_client_factory.return_value = mock_gl

            updated = await pipeline_service.monitor_pipeline_status(db_session, run.id)

        assert updated.status_flag == 2  # STATUS_WARNING
        assert "GitLab API error" in updated.status_text


# ──────────────────────────────────────────────────────────────────────
# Providers V3 (phase 4, plan stage 15): consumer link validation
# ──────────────────────────────────────────────────────────────────────


async def _seed_resource_provider(db_session: AsyncSession, **overrides) -> ResourceProvider:
    """Create a ResourceProvider row; defaults describe the platform GitLab
    (gitlab/system/internal — the only combination allowed for pipelines)."""
    values = {
        "domain": "git",
        "subtype": "gitlab",
        "category": "system",
        "direction": "internal",
        "name": "gitlab-system",
        "label": "GitLab (system)",
        "base_url": "https://gitlab.example.com",
    }
    values.update(overrides)
    if values["name"] == "gitlab-system" and "name" not in overrides:
        values["name"] = f"gitlab-system-{id(values):x}"
    provider = ResourceProvider(**values)
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)
    return provider


class TestPipelineProviderValidation:
    """pipelines.provider_id must reference any live gitlab provider (system-only
    restriction lifted by gitlab-project-management; category/direction are no
    longer enforced — the owner/type matrix lives in the service layer)."""

    @pytest.mark.asyncio
    async def test_create_with_valid_system_gitlab_provider(self, db_session: AsyncSession):
        provider = await _seed_resource_provider(db_session)
        data = PipelineCreate(name="prov-pipe-ok", provider_id=provider.id)

        pipeline = await pipeline_service.create_pipeline(db_session, data)

        assert pipeline.provider_id == provider.id

    @pytest.mark.asyncio
    async def test_create_rejects_wrong_subtype(self, db_session: AsyncSession):
        provider = await _seed_resource_provider(db_session, subtype="github", name="github-system")
        data = PipelineCreate(name="prov-pipe-github", provider_id=provider.id)

        with pytest.raises(DomainError) as exc_info:
            await pipeline_service.create_pipeline(db_session, data)
        assert "gitlab" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_create_accepts_non_system_category(self, db_session: AsyncSession):
        provider = await _seed_resource_provider(
            db_session, category="public", name="gitlab-public"
        )
        data = PipelineCreate(name="prov-pipe-public", provider_id=provider.id)

        pipeline = await pipeline_service.create_pipeline(db_session, data)

        assert pipeline.provider_id == provider.id

    @pytest.mark.asyncio
    async def test_create_accepts_external_direction(self, db_session: AsyncSession):
        provider = await _seed_resource_provider(
            db_session, direction="external", name="gitlab-external"
        )
        data = PipelineCreate(name="prov-pipe-external", provider_id=provider.id)

        pipeline = await pipeline_service.create_pipeline(db_session, data)

        assert pipeline.provider_id == provider.id

    @pytest.mark.asyncio
    async def test_create_rejects_missing_provider(self, db_session: AsyncSession):
        data = PipelineCreate(name="prov-pipe-missing", provider_id=99999)

        with pytest.raises(NotFoundError):
            await pipeline_service.create_pipeline(db_session, data)


class TestDockerTargetProviderValidation:
    """docker_image_sources.target_provider_id must reference an internal
    harbor/generic_registry provider (plan 11.3.4)."""

    @pytest.mark.asyncio
    async def test_target_provider_internal_harbor_accepted(self, db_session: AsyncSession):
        from app.services.docker import DockerRegistryService

        provider = await _seed_resource_provider(
            db_session,
            domain="docker",
            subtype="harbor",
            category="system",
            direction="internal",
            name="harbor-internal",
            base_url="https://harbor.example.com",
        )
        service = DockerRegistryService()

        # image_name=None → no network indexing happens
        source = await service.import_source_from_url(
            name="harbor-target-src",
            registry_url="https://registry-1.docker.io",
            image_name=None,
            db=db_session,
            target_provider_id=provider.id,
        )

        assert source.target_provider_id == provider.id
        # The legacy URL column is kept in sync with the provider base_url
        assert source.target_registry_url == "https://harbor.example.com"

    @pytest.mark.asyncio
    async def test_target_provider_external_rejected(self, db_session: AsyncSession):
        from app.services.docker import DockerRegistryService

        provider = await _seed_resource_provider(
            db_session,
            domain="docker",
            subtype="harbor",
            category="public",
            direction="external",
            name="harbor-external",
        )
        service = DockerRegistryService()

        with pytest.raises(BadRequestError) as exc_info:
            await service.import_source_from_url(
                name="harbor-ext-src",
                registry_url="https://registry-1.docker.io",
                image_name=None,
                db=db_session,
                target_provider_id=provider.id,
            )
        assert "internal" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_target_provider_wrong_subtype_rejected(self, db_session: AsyncSession):
        from app.services.docker import DockerRegistryService

        provider = await _seed_resource_provider(
            db_session,
            domain="docker",
            subtype="docker_hub",
            category="system",
            direction="internal",
            name="dockerhub-internal",
        )
        service = DockerRegistryService()

        with pytest.raises(BadRequestError) as exc_info:
            await service.import_source_from_url(
                name="dockerhub-tgt-src",
                registry_url="https://registry-1.docker.io",
                image_name=None,
                db=db_session,
                target_provider_id=provider.id,
            )
        assert "harbor or generic_registry" in str(exc_info.value.detail)
