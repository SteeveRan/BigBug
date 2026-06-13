"""
@file test_gitlab_instance_model.py
@description Unit tests for GitlabInstance model — verifies the pipelines
             relationship.
@dependencies backend/app/models/gitlab_instance.py
"""

from app.models.gitlab_instance import GitlabInstance
from app.models.pipeline import Pipeline


class TestGitlabInstanceModel:
    """Tests for the GitlabInstance model relationship extensions."""

    def test_gitlab_instance_with_pipelines(self):
        """GitlabInstance can have multiple Pipelines."""
        gi = GitlabInstance(name="main-gitlab", url="https://gitlab.example.com")
        pl1 = Pipeline(name="pipe-1", ref="main")
        pl2 = Pipeline(name="pipe-2", ref="v2")
        gi.pipelines.append(pl1)
        gi.pipelines.append(pl2)
        assert len(gi.pipelines) == 2
        assert gi.pipelines[0].name == "pipe-1"
        assert gi.pipelines[1].name == "pipe-2"
