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
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.pipeline_run import PipelineRun
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
                gitlab_instance_id=1,
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
        gitlab_instance_id=1,
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
    async def test_trigger_requires_gitlab_instance(self, db_session: AsyncSession):
        """trigger_pipeline raises NotFoundError when instance doesn't exist."""
        with pytest.raises(NotFoundError) as exc_info:
            await pipeline_service.trigger_pipeline(
                db_session,
                gitlab_instance_id=99999,
                gitlab_project_id=1,
                ref="main",
            )
        assert "instance" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_trigger_handles_gitlab_error(self, db_session: AsyncSession):
        """trigger_pipeline records failed run on GitLab API error."""
        from app.core.secrets import encrypt_secret
        from app.models.gitlab_instance import GitlabInstance as GitlabInstanceModel

        instance = GitlabInstanceModel(
            name="test-gitlab",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        with patch("app.services.pipeline._get_gitlab_client") as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            import gitlab

            mock_project.pipelines.create.side_effect = gitlab.GitlabError("Connection refused")
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_pipeline(
                db_session,
                gitlab_instance_id=instance.id,
                gitlab_project_id=42,
                ref="main",
            )

        assert run.status_flag == 1  # FAILED
        assert "GitLab API error" in run.status_text

    @pytest.mark.asyncio
    async def test_trigger_creates_run_record(self, db_session: AsyncSession):
        """trigger_pipeline creates PipelineRun on success."""
        from app.core.secrets import encrypt_secret
        from app.models.gitlab_instance import GitlabInstance as GitlabInstanceModel

        instance = GitlabInstanceModel(
            name="test-gitlab-success",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        with patch("app.services.pipeline._get_gitlab_client") as mock_client_factory:
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
                gitlab_instance_id=instance.id,
                gitlab_project_id=42,
                ref="main",
                variables={"KEY": "VALUE"},
                user_id=1,
            )

        assert run.status_flag == 3  # IN_PROGRESS
        assert run.gitlab_pipeline_id == 12345
        assert run.variables == {"KEY": "VALUE"}
        assert run.triggered_by_user_id == 1
        assert run.web_url == "https://gitlab.example.com/pipelines/12345"


# ──────────────────────────────────────────────────────────────────────
# update_pipeline_status
# ──────────────────────────────────────────────────────────────────────


class TestUpdatePipelineStatus:
    """Tests for update_pipeline_status()"""

    @pytest.mark.asyncio
    async def test_update_status_changes_flag(self, db_session: AsyncSession):
        """update_pipeline_status updates status_flag and status_text."""
        run = PipelineRun(
            gitlab_instance_id=1,
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
            gitlab_instance_id=1,
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
            gitlab_instance_id=1,
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
            gitlab_instance_id=1,
            project_path="group/project",
            component_path=".gitlab/components/del.yml",
        )

        await pipeline_service.delete_component(db_session, comp.id)

        with pytest.raises(NotFoundError):
            await pipeline_service.get_component(db_session, comp.id)
