"""Server-side ``.gitlab-ci.yml`` generation from a Pipeline configuration.

Produces a ``include:`` list of GitLab CI/CD components (ordered by
``PipelineComponent.order``), a ``stages:`` union extracted from component
content, and an optional raw ``extra_yaml`` block appended verbatim.

``generate_ci_from_pipeline`` is a pure function (no I/O) so it can be unit
tested with simple stub objects; ``push_pipeline_ci`` in ``_configs.py`` does the
actual GitLab file write.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from app.core.exceptions import DomainError

# stage lines in the component templates are flat (`  stage: build`); a regex is
# enough. ponytail: replace with a YAML parse if components ever nest stages.
_STAGE_RE = re.compile(r"^[ \t]{2}stage:[ \t]*(\S+)", re.MULTILINE)


def _host(base_url: str | None) -> str | None:
    if not base_url:
        return None
    try:
        return urlparse(base_url).hostname
    except ValueError:
        return None


def _component_host(component: Any) -> str | None:
    provider = getattr(component, "provider", None)
    return _host(getattr(provider, "base_url", None))


def conflicting_components(project_host: str | None, components: list[Any]) -> list[str]:
    """Return component names whose provider host differs from *project_host*.

    GitLab Components resolve against ``$CI_SERVER_FQDN``, so a pipeline project
    may only include components from the same GitLab host.
    """
    if project_host is None:
        return []
    conflicts: list[str] = []
    for comp in components:
        comp_host = _component_host(comp)
        if comp_host is not None and comp_host != project_host:
            conflicts.append(getattr(comp, "name", str(comp)))
    return conflicts


def _required_inputs(inputs_schema: dict[str, Any] | None) -> list[str]:
    """Return the names of required inputs that have no default value.

    Optional inputs arrive at trigger time as pipeline variables; only required
    inputs without a default are baked into the include block.
    """
    if not inputs_schema:
        return []
    properties: dict[str, Any] = inputs_schema.get("properties", {}) or {}
    required: list[str] = inputs_schema.get("required", []) or []
    return [key for key in required if "default" not in properties.get(key, {})]


def build_include_block(component: Any) -> str:
    """Build a single ``include`` entry for a component."""
    path = getattr(component, "project_path", None) or ""
    comp_path = getattr(component, "component_path", None) or ""
    version = getattr(component, "version", None) or "latest"
    lines = [f"  - component: $CI_SERVER_FQDN/{path}/{comp_path}@{version}"]
    inputs = _required_inputs(getattr(component, "inputs_schema", None))
    if inputs:
        lines.append("    inputs:")
        for key in inputs:
            # Required inputs are expected to be supplied as trigger variables;
            # referencing them keeps the include valid until GitLab resolves them.
            lines.append(f"      {key}: ${key}")
    return "\n".join(lines)


def extract_stages(contents: dict[int, str | None]) -> list[str]:
    """Return the union of stage names across component contents, order preserved."""
    stages: list[str] = []
    for content in contents.values():
        if not content:
            continue
        for stage in _STAGE_RE.findall(content):
            if stage not in stages:
                stages.append(stage)
    return stages


def build_ci_yaml(
    include_blocks: list[str], stages: list[str], extra_yaml: str | None = None
) -> str:
    """Assemble the final ``.gitlab-ci.yml`` string."""
    parts: list[str] = ["include:"]
    parts.extend(include_blocks)
    if stages:
        parts.append("")
        parts.append("stages:")
        parts.extend(f"  - {stage}" for stage in stages)
    if extra_yaml:
        parts.append("")
        parts.append(extra_yaml.rstrip("\n"))
    return "\n".join(parts) + "\n"


def generate_ci_from_pipeline(
    pipeline: Any,
    extra_yaml: str | None = None,
    component_contents: dict[int, str | None] | None = None,
) -> str:
    """Generate ``.gitlab-ci.yml`` for a Pipeline, raising 422 on host mismatch."""
    project = getattr(pipeline, "gitlab_project", None)
    project_host = _host(getattr(getattr(project, "provider", None), "base_url", None))

    components = list(getattr(pipeline, "components", []) or [])
    components.sort(key=lambda pc: getattr(pc, "order", 0))

    conflicts = conflicting_components(project_host, [pc.component for pc in components])
    if conflicts:
        raise DomainError(
            "Pipeline components resolve from a different GitLab host than the "
            f"pipeline project: {', '.join(conflicts)}",
            422,
        )

    include_blocks = [build_include_block(pc.component) for pc in components]
    contents = component_contents or {getattr(pc.component, "id", 0): None for pc in components}
    stages = extract_stages(contents)
    return build_ci_yaml(include_blocks, stages, extra_yaml)
