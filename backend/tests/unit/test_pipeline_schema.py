"""
@file test_pipeline_schema.py
@description Unit tests for Pipeline Pydantic schemas (v2).
             Existing PipelineRun/GitLabComponent schemas are also tested.
@dependencies app.schemas.pipeline
"""

import pytest
from pydantic import ValidationError

from app.schemas.pipeline import (
    ComponentRunRequest,
    GitLabComponentCreate,
    GitLabComponentOut,
    PipelineComponentOut,
    PipelineComponentRef,
    PipelineCreate,
    PipelineOut,
    PipelineRunCreate,
    PipelineRunOut,
    PipelineUpdate,
)


class TestPipelineComponentRef:
    """Validation of PipelineComponentRef schema."""

    def test_ref_minimal(self):
        """Create with required fields and default order."""
        ref = PipelineComponentRef(component_id=1)
        assert ref.component_id == 1
        assert ref.order == 0
        assert ref.overrides is None

    def test_ref_with_overrides(self):
        """Create with overrides dict."""
        ref = PipelineComponentRef(
            component_id=2,
            order=3,
            overrides={"timeout": "10m", "retry": "3"},
        )
        assert ref.order == 3
        assert ref.overrides == {"timeout": "10m", "retry": "3"}

    def test_ref_validates_order_non_negative(self):
        """order must be >= 0."""
        with pytest.raises(ValidationError):
            PipelineComponentRef(component_id=1, order=-1)


class TestPipelineCreate:
    """Validation of PipelineCreate schema."""

    def test_create_minimal(self):
        """Create with name only — all other fields optional."""
        data = PipelineCreate(name="default-pipeline")
        assert data.name == "default-pipeline"
        assert data.is_enabled is True
        assert data.components is None

    def test_create_with_components(self):
        """Create with inline components."""
        data = PipelineCreate(
            name="multi-component",
            provider_id=1,
            ref="main",
            components=[
                PipelineComponentRef(component_id=10, order=1),
                PipelineComponentRef(component_id=20, order=2, overrides={"env": "prod"}),
            ],
        )
        assert len(data.components) == 2
        assert data.components[0].component_id == 10
        assert data.components[1].component_id == 20

    def test_create_name_required(self):
        """name is required."""
        with pytest.raises(ValidationError):
            PipelineCreate()


class TestPipelineUpdate:
    """Validation of PipelineUpdate — all fields optional."""

    def test_update_empty(self):
        """All fields are optional."""
        data = PipelineUpdate()
        assert data.description is None
        assert data.provider_id is None

    def test_update_partial(self):
        """Update description and is_enabled."""
        data = PipelineUpdate(description="Updated", is_enabled=False)
        assert data.description == "Updated"
        assert data.is_enabled is False


class TestPipelineComponentOut:
    """Validation of PipelineComponentOut schema."""

    def test_out_has_component_nested(self):
        """PipelineComponentOut can hold a nested GitLabComponentOut."""
        fields = set(PipelineComponentOut.model_fields.keys())
        expected = {"id", "pipeline_id", "component_id", "order", "overrides", "component"}
        assert fields == expected

    def test_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert PipelineComponentOut.model_config.get("from_attributes") is True


class TestPipelineOut:
    """Validation of PipelineOut schema."""

    def test_out_has_expected_fields(self):
        """Verify all expected fields including nested relations."""
        fields = set(PipelineOut.model_fields.keys())
        expected = {
            "id",
            "name",
            "description",
            "provider_id",
            "gitlab_project_id",
            "ref",
            "default_variables",
            "is_default",
            "is_enabled",
            "is_deleted",
            "deleted_at",
            "created_at",
            "updated_at",
            "components",
            "provider",
        }
        assert fields == expected

    def test_out_components_default_empty(self):
        """components defaults to empty list."""
        assert PipelineOut.model_fields["components"].default == []

    def test_out_from_attributes_config(self):
        """model_config enables from_attributes."""
        assert PipelineOut.model_config.get("from_attributes") is True


# ──── Existing schemas — regression tests ──────────────────────────────


class TestPipelineRunCreate:
    """Regression: PipelineRunCreate still works."""

    def test_create(self):
        data = PipelineRunCreate(
            provider_id=1,
            gitlab_project_id=123,
            ref="main",
        )
        assert data.ref == "main"
        assert data.variables == {}


class TestPipelineRunOut:
    """Regression: PipelineRunOut still works."""

    def test_out_fields(self):
        fields = set(PipelineRunOut.model_fields.keys())
        assert "id" in fields
        assert "gitlab_pipeline_id" in fields
        assert "component_id" in fields


class TestGitLabComponentCreate:
    """Regression: GitLabComponentCreate still works."""

    def test_create_minimal(self):
        data = GitLabComponentCreate(
            name="test-component",
            provider_id=1,
            project_path="my-group/my-project",
            component_path="templates/component.yml",
        )
        assert data.name == "test-component"


class TestGitLabComponentOut:
    """Regression: GitLabComponentOut still works."""

    def test_out_fields(self):
        fields = set(GitLabComponentOut.model_fields.keys())
        assert "id" in fields
        assert "name" in fields
        assert "is_enabled" in fields


class TestComponentRunRequest:
    """Regression: ComponentRunRequest still works."""

    def test_request_defaults(self):
        data = ComponentRunRequest()
        assert data.ref == "main"
        assert data.inputs == {}
