"""
@file test_gitlab_project_model.py
@description Unit tests for the GitlabProject and RoleScopeGitlabProject models —
             verifies enums, field defaults, and relationships.
@dependencies backend/app/models/gitlab_project.py, backend/app/models/role_scope.py
"""

from app.models.gitlab_project import (
    GitlabProject,
    GitlabProjectType,
    ProjectVisibility,
)
from app.models.pipeline import Pipeline
from app.models.role_scope import RoleScopeGitlabProject


class TestGitlabProjectEnums:
    def test_project_types(self):
        assert GitlabProjectType.components.value == "components"
        assert GitlabProjectType.pipelines.value == "pipelines"

    def test_project_visibility(self):
        assert ProjectVisibility.owner.value == "owner"
        assert ProjectVisibility.team.value == "team"
        assert ProjectVisibility.public.value == "public"


class TestGitlabProjectModel:
    def test_create_basic(self):
        project = GitlabProject(
            name="components",
            path="components",
            namespace_path="bigbug-mirrors",
            full_path="bigbug-mirrors/components",
            project_type=GitlabProjectType.components,
            provider_id=7,
        )
        assert project.name == "components"
        assert project.full_path == "bigbug-mirrors/components"
        assert project.project_type is GitlabProjectType.components

    def test_create_pipelines_type(self):
        project = GitlabProject(
            name="pipelines",
            path="pipelines",
            namespace_path="bigbug-mirrors",
            full_path="bigbug-mirrors/pipelines",
            project_type=GitlabProjectType.pipelines,
            provider_id=8,
            status_flag=4,
        )
        assert project.project_type is GitlabProjectType.pipelines
        assert project.status_flag == 4  # Pending

    def test_column_defaults(self):
        """``visibility``, ``status_flag`` and ``default_branch`` have defaults."""
        visibility_default = GitlabProject.__table__.c.visibility.default
        assert visibility_default is not None
        assert visibility_default.arg is ProjectVisibility.owner

        status_default = GitlabProject.__table__.c.status_flag.default
        assert status_default is not None
        assert status_default.arg == 0

        branch_default = GitlabProject.__table__.c.default_branch.default
        assert branch_default is not None
        assert branch_default.arg == "main"

        is_deleted_default = GitlabProject.__table__.c.is_deleted.default
        assert is_deleted_default is not None
        assert is_deleted_default.arg is False

    def test_relationships(self):
        project = GitlabProject(
            name="components",
            path="components",
            namespace_path="bigbug-mirrors",
            full_path="bigbug-mirrors/components",
            project_type=GitlabProjectType.components,
            provider_id=7,
        )
        pipeline = Pipeline(name="test-pipe", ref="main", default_variables={})
        project.pipelines.append(pipeline)
        assert len(project.pipelines) == 1
        assert project.pipelines[0] is pipeline


class TestRoleScopeGitlabProjectModel:
    def test_scope_creation(self):
        scope = RoleScopeGitlabProject(role_id=1, gitlab_project_id=2)
        assert scope.role_id == 1
        assert scope.gitlab_project_id == 2

    def test_scope_repr(self):
        scope = RoleScopeGitlabProject(role_id=1, gitlab_project_id=2)
        assert "role_id=1" in repr(scope)
        assert "gitlab_project_id=2" in repr(scope)
