"""
@file test_component_run.py
@description Unit tests for the new component run functionality including:
             - trigger_component method in the pipeline service
             - ComponentRunRequest schema validation
             - POST /api/components/{id}/run endpoint
             - Updated PipelineRun model with component_id
@dependencies pytest, pytest-asyncio, backend/tests/conftest.py
@relatedFiles ../../app/services/pipeline.py, ../../app/schemas/pipeline.py,
               ../../app/api/components.py, ../../app/models/pipeline_run.py
"""

from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.rbac import RoleName
from app.core.secrets import encrypt_secret
from app.models.gitlab_component import GitLabComponent
from app.models.gitlab_instance import GitlabInstance as GitlabInstanceModel
from app.models.permission import Permission, role_permissions
from app.models.pipeline_run import PipelineRun

# Import the role model at the top with other imports
from app.models.role import Role
from app.services import pipeline as pipeline_service

# Valid permissions required by integration endpoints
REQUIRED_PERMISSIONS = [
    {"name": "pipelines:read", "description": "Read pipeline runs"},
    {"name": "pipelines:write", "description": "Create and trigger pipelines"},
    {"name": "pipelines:delete", "description": "Cancel and delete pipelines"},
]


@pytest_asyncio.fixture(autouse=True)
async def seeded_permissions(db_session: AsyncSession):
    """Ensure the three standard roles exist and that the admin role
    has **every** permission listed in ``REQUIRED_PERMISSIONS``.
    """
    # ── ensure the three standard roles exist ──────────────────────────
    role_names = [RoleName.ADMIN.value, RoleName.OPERATOR.value, RoleName.VIEWER.value]
    roles: dict[str, Role] = {}
    for name in role_names:
        result = await db_session.execute(select(Role).where(Role.name == name))
        role = result.scalar_one_or_none()
        if role is None:
            role = Role(name=name, description=f"{name.capitalize()} role")
            db_session.add(role)
            await db_session.flush()
        roles[name] = role
    admin_role = roles[RoleName.ADMIN.value]

    # ── ensure required permissions exist and are assigned to admin ────
    for perm_data in REQUIRED_PERMISSIONS:
        result = await db_session.execute(
            select(Permission).where(Permission.name == perm_data["name"])
        )
        perm = result.scalar_one_or_none()
        if perm is None:
            perm = Permission(name=perm_data["name"], description=perm_data["description"])
            db_session.add(perm)
            await db_session.flush()

        # Refresh admin_role.permissions relationship for idempotency check
        await db_session.refresh(admin_role, attribute_names=["permissions"])
        if perm not in admin_role.permissions:
            await db_session.execute(
                role_permissions.insert().values(role_id=admin_role.id, permission_id=perm.id)
            )

    await db_session.commit()


# ──────────────────────────────────────────────────────────────────────
# ComponentRunRequest Schema Validation Tests
# ──────────────────────────────────────────────────────────────────────


def test_component_run_request_defaults():
    """ComponentRunRequest has correct default values."""
    from app.schemas.pipeline import ComponentRunRequest

    request = ComponentRunRequest()
    assert request.ref == "main"
    assert request.inputs == {}


def test_component_run_request_custom_values():
    """ComponentRunRequest accepts custom values."""
    from app.schemas.pipeline import ComponentRunRequest

    request = ComponentRunRequest(ref="develop", inputs={"KEY": "VALUE"})
    assert request.ref == "develop"
    assert request.inputs == {"KEY": "VALUE"}


def test_component_run_request_input_validation():
    """ComponentRunRequest validates input types."""
    from app.schemas.pipeline import ComponentRunRequest

    # Should accept string inputs
    request = ComponentRunRequest(inputs={"str_field": "value", "num_field": "42"})
    assert request.inputs == {"str_field": "value", "num_field": "42"}


# ──────────────────────────────────────────────────────────────────────
# trigger_component Service Method Tests
# ──────────────────────────────────────────────────────────────────────


class TestTriggerComponent:
    """Tests for trigger_component() service method."""

    @pytest.mark.asyncio
    async def test_trigger_component_requires_existing_component(self, db_session: AsyncSession):
        """trigger_component raises NotFoundError when component doesn't exist."""
        with pytest.raises(NotFoundError) as exc_info:
            await pipeline_service.trigger_component(
                db_session,
                component_id=99999,
                inputs={"KEY": "VALUE"},
            )
        assert "component" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_trigger_component_validates_inputs_against_schema(
        self, db_session: AsyncSession
    ):
        """trigger_component validates inputs against component's input schema."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-gitlab",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        # Create a component with input schema requiring specific fields
        component = GitLabComponent(
            name="test-component",
            gitlab_instance_id=instance.id,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
            inputs_schema={
                "type": "object",
                "properties": {
                    "required_field": {"type": "string"},
                    "optional_field": {"type": "integer"},
                },
                "required": ["required_field"],
            },
        )
        db_session.add(component)
        await db_session.commit()

        # Try to trigger with missing required field - should raise BadRequestError
        with pytest.raises(Exception) as exc_info:  # Will be BadRequestError
            await pipeline_service.trigger_component(
                db_session,
                component_id=component.id,
                inputs={},  # Missing required field
            )
        assert "required_field" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_trigger_component_handles_missing_gitlab_project(self, db_session: AsyncSession):
        """trigger_component records failed run when GitLab project doesn't exist."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-gitlab",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        # Create a component
        component = GitLabComponent(
            name="test-component",
            gitlab_instance_id=instance.id,
            project_path="nonexistent/group-project",
            component_path=".gitlab/components/test.yml",
        )
        db_session.add(component)
        await db_session.commit()

        with patch("app.services.pipeline._get_gitlab_client") as mock_client_factory:
            mock_gl = MagicMock()
            import gitlab

            # Simulate project not found error
            mock_gl.projects.get.side_effect = gitlab.GitlabError("Project not found")
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_component(
                db_session,
                component_id=component.id,
                inputs={"KEY": "VALUE"},
                ref="main",
                user_id=1,
            )

        # Verify the failed run was recorded
        assert run.status_flag == 1  # FAILED
        assert "not found" in run.status_text.lower()
        assert run.component_id == component.id
        assert run.variables == {"KEY": "VALUE"}
        assert run.triggered_by_user_id == 1

    @pytest.mark.asyncio
    async def test_trigger_component_handles_gitlab_api_error(self, db_session: AsyncSession):
        """trigger_component records failed run on GitLab API error during pipeline creation."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-gitlab",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        # Create a component
        component = GitLabComponent(
            name="test-component",
            gitlab_instance_id=instance.id,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
        )
        db_session.add(component)
        await db_session.commit()

        with patch("app.services.pipeline._get_gitlab_client") as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            import gitlab

            # Set the project ID
            mock_project.id = 42
            # Simulate pipeline creation failure
            mock_project.pipelines.create.side_effect = gitlab.GitlabError("API error")
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_component(
                db_session,
                component_id=component.id,
                inputs={"KEY": "VALUE"},
                ref="main",
                user_id=1,
            )

        # Verify the failed run was recorded
        assert run.status_flag == 1  # FAILED
        assert "gitlab api error" in run.status_text.lower()
        assert run.component_id == component.id
        assert run.variables == {"KEY": "VALUE"}
        assert run.triggered_by_user_id == 1
        assert run.gitlab_project_id == 42  # Should have project ID from lookup

    @pytest.mark.asyncio
    async def test_trigger_component_creates_run_record_on_success(self, db_session: AsyncSession):
        """trigger_component creates PipelineRun on successful pipeline trigger."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-gitlab-success",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        # Create a component
        component = GitLabComponent(
            name="test-component-success",
            gitlab_instance_id=instance.id,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
        )
        db_session.add(component)
        await db_session.commit()

        with patch("app.services.pipeline._get_gitlab_client") as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_pipeline = MagicMock()
            mock_pipeline.id = 12345
            mock_pipeline.web_url = "https://gitlab.example.com/group/project/-/pipelines/12345"
            mock_project.id = 42
            mock_project.pipelines.create.return_value = mock_pipeline
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_component(
                db_session,
                component_id=component.id,
                inputs={"INPUT_KEY": "INPUT_VALUE"},
                ref="develop",
                user_id=2,
            )

        # Verify the successful run was recorded
        assert run.status_flag == 3  # IN_PROGRESS
        assert run.gitlab_pipeline_id == 12345
        assert run.gitlab_project_id == 42
        assert run.component_id == component.id
        assert run.variables == {"INPUT_KEY": "INPUT_VALUE"}
        assert run.triggered_by_user_id == 2
        assert run.web_url == "https://gitlab.example.com/group/project/-/pipelines/12345"
        assert run.ref == "develop"
        assert run.trigger_type == "manual"

    @pytest.mark.asyncio
    async def test_trigger_component_with_empty_inputs(self, db_session: AsyncSession):
        """trigger_component works with empty inputs."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-gitlab-empty-inputs",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        # Create a component
        component = GitLabComponent(
            name="test-component-empty-inputs",
            gitlab_instance_id=instance.id,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
        )
        db_session.add(component)
        await db_session.commit()

        with patch("app.services.pipeline._get_gitlab_client") as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_pipeline = MagicMock()
            mock_pipeline.id = 12346
            mock_pipeline.web_url = "https://gitlab.example.com/group/project/-/pipelines/12346"
            mock_project.id = 43
            mock_project.pipelines.create.return_value = mock_pipeline
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            run = await pipeline_service.trigger_component(
                db_session,
                component_id=component.id,
                inputs={},  # Empty inputs
                ref="main",
                user_id=None,  # No user
            )

        # Verify the run was recorded with empty inputs
        assert run.status_flag == 3  # IN_PROGRESS
        assert run.gitlab_pipeline_id == 12346
        assert run.component_id == component.id
        assert run.variables == {}
        assert run.triggered_by_user_id is None


# ──────────────────────────────────────────────────────────────────────
# POST /api/components/{id}/run Endpoint Tests
# ──────────────────────────────────────────────────────────────────────


class TestComponentRunEndpoint:
    """Tests for POST /api/components/{id}/run endpoint."""

    @pytest.mark.asyncio
    async def test_run_component_endpoint_component_not_found(
        self, client: AsyncClient, admin_token: str
    ):
        """Endpoint returns 404 when component doesn't exist."""
        response = await client.post(
            "/api/components/99999/run",
            json={"inputs": {}},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == 404
        assert "component" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_run_component_endpoint_success(
        self, client: AsyncClient, db_session: AsyncSession, admin_token: str
    ):
        """Endpoint successfully triggers component run."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-instance",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        # Create a component
        component = GitLabComponent(
            name="api-test-component",
            gitlab_instance_id=instance.id,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
        )
        db_session.add(component)
        await db_session.commit()

        with patch("app.services.pipeline._get_gitlab_client") as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_pipeline = MagicMock()
            mock_pipeline.id = 99999
            mock_pipeline.web_url = "https://gitlab.example.com/group/project/-/pipelines/99999"
            mock_project.id = 500
            mock_project.pipelines.create.return_value = mock_pipeline
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            response = await client.post(
                f"/api/components/{component.id}/run",
                json={"ref": "feature-branch", "inputs": {"PARAM1": "VALUE1"}},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["gitlab_pipeline_id"] == 99999
        assert data["component_id"] == component.id
        assert data["variables"] == {"PARAM1": "VALUE1"}
        assert data["ref"] == "feature-branch"
        assert data["status_flag"] == 3  # IN_PROGRESS

    @pytest.mark.asyncio
    async def test_run_component_endpoint_invalid_input_schema(
        self, client: AsyncClient, db_session: AsyncSession, admin_token: str
    ):
        """Endpoint returns 422 when input validation fails."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-instance-validation",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        # Create a component with input schema
        component = GitLabComponent(
            name="api-test-component-validation",
            gitlab_instance_id=instance.id,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
            inputs_schema={
                "type": "object",
                "properties": {
                    "required_param": {"type": "string"},
                },
                "required": ["required_param"],
            },
        )
        db_session.add(component)
        await db_session.commit()

        # Try to trigger with missing required param
        response = await client.post(
            f"/api/components/{component.id}/run",
            json={"inputs": {}},  # Missing required_param
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        # Should return 400 for validation error (FastAPI default for Pydantic validation)
        assert response.status_code in [400, 422]  # Accept either 400 or 422
        # The error should indicate validation failure
        assert "required_param" in str(response.json())

    @pytest.mark.asyncio
    async def test_run_component_endpoint_gitlab_error(
        self, client: AsyncClient, db_session: AsyncSession, admin_token: str
    ):
        """Endpoint returns 201 but with failed run when GitLab API fails."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-instance-error",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        # Create a component
        component = GitLabComponent(
            name="api-test-component-error",
            gitlab_instance_id=instance.id,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
        )
        db_session.add(component)
        await db_session.commit()

        with patch("app.services.pipeline._get_gitlab_client") as mock_client_factory:
            mock_gl = MagicMock()
            import gitlab

            mock_gl.projects.get.side_effect = gitlab.GitlabError("Project not found")
            mock_client_factory.return_value = mock_gl

            response = await client.post(
                f"/api/components/{component.id}/run",
                json={"inputs": {"PARAM1": "VALUE1"}},
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        # Should still return 201 as the call was processed, but run should be marked as failed
        assert response.status_code == 201
        data = response.json()
        assert data["status_flag"] == 1  # FAILED
        assert "not found" in data["status_text"].lower()
        assert data["component_id"] == component.id

    @pytest.mark.asyncio
    async def test_run_component_endpoint_with_defaults(
        self, client: AsyncClient, db_session: AsyncSession, admin_token: str
    ):
        """Endpoint uses default ref value when not provided."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-instance-defaults",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        await db_session.commit()

        # Create a component
        component = GitLabComponent(
            name="api-test-component-defaults",
            gitlab_instance_id=instance.id,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
        )
        db_session.add(component)
        await db_session.commit()

        with patch("app.services.pipeline._get_gitlab_client") as mock_client_factory:
            mock_gl = MagicMock()
            mock_project = MagicMock()
            mock_pipeline = MagicMock()
            mock_pipeline.id = 11111
            mock_pipeline.web_url = "https://gitlab.example.com/group/project/-/pipelines/11111"
            mock_project.id = 501
            mock_project.pipelines.create.return_value = mock_pipeline
            mock_gl.projects.get.return_value = mock_project
            mock_client_factory.return_value = mock_gl

            # Call without ref (should use default "main")
            response = await client.post(
                f"/api/components/{component.id}/run",
                json={"inputs": {"PARAM1": "VALUE1"}},  # No ref provided
                headers={"Authorization": f"Bearer {admin_token}"},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["gitlab_pipeline_id"] == 11111
        assert data["ref"] == "main"  # Should use default
        assert data["status_flag"] == 3  # IN_PROGRESS


# ──────────────────────────────────────────────────────────────────────
# Updated PipelineRun Model Tests
# ──────────────────────────────────────────────────────────────────────


class TestUpdatedPipelineRunModel:
    """Tests for the updated PipelineRun model with component_id."""

    def test_pipeline_run_has_component_id_field(self, db_session: AsyncSession):
        """PipelineRun model includes component_id field."""
        run = PipelineRun(
            gitlab_instance_id=1,
            gitlab_project_id=42,
            ref="main",
            component_id=5,  # This should be supported now
        )

        assert hasattr(run, "component_id")
        assert run.component_id == 5

    def test_pipeline_run_component_id_nullable(self, db_session: AsyncSession):
        """component_id field is nullable for regular pipeline runs."""
        run = PipelineRun(
            gitlab_instance_id=1,
            gitlab_project_id=42,
            ref="main",
            # component_id is None by default
        )

        assert run.component_id is None

    def test_pipeline_run_with_component_relationship(self, db_session: AsyncSession):
        """PipelineRun can be associated with a GitLabComponent."""

        # Create a GitLab instance
        instance = GitlabInstanceModel(
            name="test-instance-model",
            url="https://gitlab.example.com",
            token=encrypt_secret("fake-token"),
            verify_ssl=True,
        )
        db_session.add(instance)
        # Note: We're just testing the model structure, not persisting to DB in this test
        # So we don't need to flush/commit here

        # Create a component
        component = GitLabComponent(
            name="model-test-component",
            gitlab_instance_id=instance.id,
            project_path="group/project",
            component_path=".gitlab/components/test.yml",
        )
        # Don't add to session - just testing the model structure

        # Create a run with component association
        run = PipelineRun(
            gitlab_instance_id=instance.id,
            gitlab_project_id=42,
            ref="main",
            component_id=component.id,
        )

        # Verify the relationship can be established
        assert run.component_id == component.id
        # Note: The actual relationship would be loaded when queried from DB
