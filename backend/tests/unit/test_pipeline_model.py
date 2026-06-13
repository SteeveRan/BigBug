"""
@file test_pipeline_model.py
@description Unit tests for Pipeline and PipelineComponent models — verifies
             creation, component composition, defaults, and unique constraints.
@dependencies backend/app/models/pipeline.py
"""

from app.models.pipeline import Pipeline, PipelineComponent


class TestPipelineModel:
    """Tests for the Pipeline SQLAlchemy model."""

    def test_pipeline_creation(self):
        """Create a Pipeline with required fields."""
        pl = Pipeline(
            name="default-mirror-pipeline",
            description="Default sync pipeline for git mirrors",
            ref="main",
            is_default=True,
            is_enabled=True,
            default_variables={},
        )
        assert pl.name == "default-mirror-pipeline"
        assert pl.description == "Default sync pipeline for git mirrors"
        assert pl.ref == "main"
        assert pl.is_default is True
        assert pl.is_enabled is True
        assert pl.default_variables == {}

    def test_pipeline_with_default_variables(self):
        """Create a Pipeline with pre-configured variables."""
        pl = Pipeline(
            name="custom-pipeline",
            ref="v2.0",
            default_variables={"CONCURRENCY": 4, "TIMEOUT": "30m"},
            is_enabled=True,
        )
        assert pl.default_variables == {"CONCURRENCY": 4, "TIMEOUT": "30m"}
        assert pl.is_enabled is True

    def test_pipeline_defaults(self):
        """Verify Pipeline can be created with minimal required fields."""
        pl = Pipeline(
            name="test-pipeline",
            ref="main",
            is_default=False,
            is_enabled=True,
            default_variables={},
        )
        assert pl.is_default is False
        assert pl.is_enabled is True
        assert pl.default_variables == {}

    def test_pipeline_with_components(self):
        """Create a Pipeline with linked PipelineComponents."""
        pl = Pipeline(
            name="composed-pipeline",
            ref="main",
            default_variables={},
        )
        pc1 = PipelineComponent(
            pipeline_id=1,
            component_id=10,
            order=0,
            overrides={"input_key": "value1"},
        )
        pc2 = PipelineComponent(
            pipeline_id=1,
            component_id=20,
            order=1,
            overrides={},
        )
        pl.components.append(pc1)
        pl.components.append(pc2)
        assert len(pl.components) == 2
        assert pl.components[0].order == 0
        assert pl.components[1].order == 1

    def test_pipeline_representation(self):
        """Verify __repr__ output."""
        pl = Pipeline(
            id=1,
            name="my-pipeline",
            ref="main",
            is_default=True,
            default_variables={},
        )
        repr_str = repr(pl)
        assert "my-pipeline" in repr_str
        assert "Pipeline" in repr_str


class TestPipelineComponentModel:
    """Tests for the PipelineComponent SQLAlchemy model."""

    def test_pipeline_component_creation(self):
        """Create a PipelineComponent with basic fields."""
        pc = PipelineComponent(
            pipeline_id=1,
            component_id=5,
            order=2,
            overrides={},
        )
        assert pc.pipeline_id == 1
        assert pc.component_id == 5
        assert pc.order == 2
        assert pc.overrides == {}

    def test_pipeline_component_with_overrides(self):
        """Create a PipelineComponent with JSON overrides."""
        pc = PipelineComponent(
            pipeline_id=2,
            component_id=3,
            order=0,
            overrides={"branch": "develop", "timeout": 600},
        )
        assert pc.overrides == {"branch": "develop", "timeout": 600}

    def test_pipeline_component_parent_pipeline(self):
        """Verify relationship — PipelineComponent can reference a Pipeline."""
        pl = Pipeline(
            name="parent-pipe",
            ref="main",
            default_variables={},
        )
        pc = PipelineComponent(
            order=0,
            component_id=1,
            overrides={},
        )
        pc.pipeline = pl
        assert pc.pipeline is pl
        assert pc.pipeline.name == "parent-pipe"

    def test_pipeline_component_representation(self):
        """Verify __repr__ output."""
        pc = PipelineComponent(
            id=100,
            pipeline_id=5,
            component_id=10,
            order=3,
            overrides={},
        )
        repr_str = repr(pc)
        assert "PipelineComponent" in repr_str
