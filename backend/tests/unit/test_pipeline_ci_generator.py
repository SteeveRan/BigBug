"""
@file test_pipeline_ci_generator.py
@description Unit tests for the server-side ``.gitlab-ci.yml`` generator
              (``app.services.pipeline._ci``) and the component preset input
              schema extractor. Pure functions only — no GitLab API, no DB.
@dependencies backend/app/services/pipeline/_ci.py,
              backend/app/services/gitlab_projects/presets.py
"""

from types import SimpleNamespace

import pytest

from app.core.exceptions import DomainError
from app.services.pipeline._ci import (
    build_ci_yaml,
    build_include_block,
    conflicting_components,
    extract_stages,
    generate_ci_from_pipeline,
)


def _component(
    name="comp",
    project_path="bigbug-mirrors/components",
    component_path="templates/foo.yml",
    version="1.2.0",
    inputs_schema=None,
    host="gitlab.example.com",
):
    provider = SimpleNamespace(base_url=f"https://{host}")
    return SimpleNamespace(
        id=1,
        name=name,
        provider=provider,
        project_path=project_path,
        component_path=component_path,
        version=version,
        inputs_schema=inputs_schema,
    )


def _pipeline_component(component, order=0):
    return SimpleNamespace(component=component, order=order)


def _pipeline(components, host="gitlab.example.com"):
    provider = SimpleNamespace(base_url=f"https://{host}")
    project = SimpleNamespace(provider=provider)
    return SimpleNamespace(gitlab_project=project, components=components)


class TestBuildIncludeBlock:
    def test_default_version_is_latest(self):
        comp = _component(version=None)
        block = build_include_block(comp)
        assert (
            "component: $CI_SERVER_FQDN/bigbug-mirrors/components/templates/foo.yml@latest" in block
        )

    def test_required_inputs_without_default_are_injected(self):
        comp = _component(
            inputs_schema={
                "properties": {
                    "image": {"type": "string"},
                    "tags": {"type": "string", "default": "latest"},
                },
                "required": ["image", "tags"],
            }
        )
        block = build_include_block(comp)
        assert "inputs:" in block
        assert "image: $image" in block
        # Optional input (has default) must not be baked into the include block.
        assert "tags:" not in block

    def test_no_inputs_when_schema_empty(self):
        comp = _component(inputs_schema={})
        block = build_include_block(comp)
        assert "inputs:" not in block


class TestExtractStages:
    def test_union_preserves_order_and_deduplicates(self):
        contents = {
            1: "  stage: build\n  stage: sign\n",
            2: "  stage: sign\n  stage: notify\n",
        }
        assert extract_stages(contents) == ["build", "sign", "notify"]

    def test_skips_missing_content(self):
        assert extract_stages({1: None}) == []


class TestBuildCiYaml:
    def test_full_assembly(self):
        yaml = build_ci_yaml(
            ["  - component: $CI_SERVER_FQDN/a/b@1.0.0"],
            ["build", "notify"],
            extra_yaml="variables:\n  FOO: bar",
        )
        assert yaml.startswith("include:\n")
        assert "stages:\n  - build\n  - notify" in yaml
        assert "variables:\n  FOO: bar" in yaml

    def test_no_stages_no_extra(self):
        yaml = build_ci_yaml([], [])
        assert yaml == "include:\n"


class TestConflictingComponents:
    def test_different_host_is_reported(self):
        comps = [_component(name="bad", host="other.example.com")]
        assert conflicting_components("gitlab.example.com", comps) == ["bad"]

    def test_same_host_no_conflict(self):
        comps = [_component(name="ok", host="gitlab.example.com")]
        assert conflicting_components("gitlab.example.com", comps) == []

    def test_none_project_host_never_conflicts(self):
        comps = [_component(name="ok", host="gitlab.example.com")]
        assert conflicting_components(None, comps) == []


class TestGenerateCiFromPipeline:
    def test_generates_sorted_include(self):
        pipeline = _pipeline(
            [
                _pipeline_component(_component(component_path="templates/second.yml"), order=2),
                _pipeline_component(_component(component_path="templates/first.yml"), order=1),
            ]
        )
        yaml = generate_ci_from_pipeline(pipeline)
        # order 1 must appear before order 2
        assert yaml.index("first.yml") < yaml.index("second.yml")

    def test_host_mismatch_raises_422(self):
        pipeline = _pipeline(
            [_pipeline_component(_component(name="bad", host="other.example.com"))]
        )
        with pytest.raises(DomainError) as exc_info:
            generate_ci_from_pipeline(pipeline)
        assert exc_info.value.status_code == 422
        assert "bad" in exc_info.value.detail


class TestPresetInputsSchema:
    def test_extract_required_and_default(self):
        from app.services.gitlab_projects.presets import extract_inputs_schema

        content = (
            "spec:\n"
            "  inputs:\n"
            "    image:\n"
            "      description: 'The image to copy.'\n"
            "    tags:\n"
            '      default: "latest"\n'
            "      description: 'Tags.'\n"
        )
        schema = extract_inputs_schema(content)
        props = schema["properties"]
        assert props["image"]["type"] == "string"
        assert "default" not in props["image"]
        assert schema["required"] == ["image"]
        assert props["tags"]["default"] == "latest"

    def test_empty_for_pipeline_templates_without_spec(self):
        from app.services.gitlab_projects.presets import extract_inputs_schema

        assert extract_inputs_schema("stages:\n  - build\n") == {}
