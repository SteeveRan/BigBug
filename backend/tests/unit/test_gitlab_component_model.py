"""
@file test_gitlab_component_model.py
@description Unit tests for GitLabComponent model — verifies the
             pipeline_components relationship.
@dependencies backend/app/models/gitlab_component.py
"""

from app.models.gitlab_component import GitLabComponent
from app.models.pipeline import Pipeline, PipelineComponent


class TestGitLabComponentModel:
    """Tests for the GitLabComponent model relationship extensions."""

    def test_gitlab_component_with_pipeline_components(self):
        """GitLabComponent can be used in multiple PipelineComponents."""
        comp = GitLabComponent(
            name="mirror-component",
            provider_id=1,
            project_path="ci/components",
            component_path="mirror.yml",
        )
        pl = Pipeline(name="pipe-1", ref="main", default_variables={})
        pc = PipelineComponent(order=0, component_id=1, overrides={})
        pc.pipeline = pl
        pc.component = comp
        # back_populates automatically adds pc to comp.pipeline_components
        assert len(comp.pipeline_components) == 1
        assert comp.pipeline_components[0].pipeline is pl
