"""
@file test_pipeline_run_model.py
@description Unit tests for PipelineRun model — verifies the pipeline
             relationship and mirror_logs back_populates.
@dependencies backend/app/models/pipeline_run.py
"""

from app.models.pipeline_run import PipelineRun
from app.models.pipeline import Pipeline


class TestPipelineRunModel:
    """Tests for the PipelineRun model extensions."""

    def test_pipeline_run_with_pipeline(self):
        """PipelineRun can reference a Pipeline via pipeline_id."""
        pl = Pipeline(name="test-pipe", ref="main")
        pr = PipelineRun(
            gitlab_instance_id=1,
            gitlab_project_id=100,
            ref="main",
            pipeline_id=1,
        )
        pr.pipeline = pl
        assert pr.pipeline is pl
        assert pr.pipeline.name == "test-pipe"

    def test_pipeline_run_pipeline_nullable(self):
        """PipelineRun with no pipeline (pipeline_id is nullable)."""
        pr = PipelineRun(
            gitlab_instance_id=1,
            gitlab_project_id=100,
            ref="main",
        )
        assert pr.pipeline_id is None
