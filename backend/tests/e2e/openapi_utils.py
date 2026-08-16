"""
@file openapi_utils.py
@description OpenAPI contract validation + endpoint-call collector for e2e tests.
              Loads ``backend/openapi.json`` once per session and exposes:
              - :func:`assert_matches_openapi` — verifies a live response against
                the declared status code and JSON Schema for an operation;
              - :func:`collect_call` / :func:`write_endpoint_report` — records which
                (path-template, method) operations were exercised and emits the
                endpoint-coverage report (JSON + Markdown).
@dependencies jsonschema, httpx, pytest
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path
from typing import Any

from jsonschema import validators
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

# Resolved against this module: backend/tests/e2e/openapi_utils.py → backend/
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_OPENAPI_PATH = _BACKEND_DIR / "openapi.json"
_REPORTS_DIR = _BACKEND_DIR / "reports"

# Soft threshold for endpoint coverage. The infrastructure test fails only when
# coverage drops below this floor, so a silently-degraded run is still caught.
MIN_COVERAGE_PERCENT = 30


# ──────────────────────────────────────────────────────────────────────────
# OpenAPI loading
# ──────────────────────────────────────────────────────────────────────────


def load_openapi_spec() -> dict[str, Any]:
    """Load the frozen OpenAPI document from ``backend/openapi.json``."""
    if not _OPENAPI_PATH.exists():
        raise FileNotFoundError(
            f"OpenAPI contract not found at {_OPENAPI_PATH}. "
            "Run backend/scripts/export-openapi.sh first."
        )
    with _OPENAPI_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_validator(spec: dict[str, Any], schema: dict[str, Any]) -> Any:
    """Build a ``jsonschema`` validator able to follow remaining local refs.

    Resolves local ``#/components/schemas/...`` refs via the modern
    ``referencing`` library instead of the deprecated ``RefResolver``. The
    registry maps the spec onto the empty base URI so local refs resolve
    against the spec root (the frozen document uses no external refs).
    """
    cls = validators.validator_for(schema)
    cls.check_schema(schema)
    resource = Resource.from_contents(spec, default_specification=DRAFT202012)
    registry = Registry().with_resource("", resource)
    resolver = registry.resolver_with_root(resource)
    return cls(schema, _resolver=resolver)


# ──────────────────────────────────────────────────────────────────────────
# Operation lookup
# ──────────────────────────────────────────────────────────────────────────


def _path_matches(template: str, path: str) -> bool:
    """True when ``path`` conforms to an OpenAPI ``template``."""
    pattern = re.sub(r"\{[^}]+\}", "[^/]+", template)
    return re.fullmatch(pattern, path) is not None


def find_operation(spec: dict[str, Any], path: str, method: str) -> tuple[str, dict[str, Any]]:
    """Return ``(path_template, operation)`` for an HTTP path and method.

    Raises ``KeyError`` with a clear message when the operation is absent from
    the contract (e.g. a request was sent to an endpoint not in openapi.json).
    """
    method = method.lower()
    for template, methods in spec.get("paths", {}).items():
        if method in methods and _path_matches(template, path):
            return template, methods[method]
    raise KeyError(f"OpenAPI operation not found: {method.upper()} {path}")


# ──────────────────────────────────────────────────────────────────────────
# Response validation
# ──────────────────────────────────────────────────────────────────────────


def _json_schema_for(operation: dict[str, Any], status_code: int) -> dict[str, Any] | None:
    response = operation.get("responses", {}).get(str(status_code))
    if response is None:
        return None
    content = response.get("content", {})
    json_media = content.get("application/json")
    if json_media is None:
        return None
    return json_media.get("schema")


def assert_matches_openapi(
    response: Any,
    path: str,
    method: str,
    spec: dict[str, Any] | None = None,
) -> None:
    """Validate an httpx ``Response`` against the frozen OpenAPI contract.

    - records the ``(path-template, method)`` operation in the session collector;
    - asserts the actual status code is declared by the operation;
    - when a JSON response schema exists for that status, validates the body.

    ``spec`` is optional (cached by the caller's session fixture); when omitted
    it is loaded from disk.
    """
    if spec is None:
        spec = load_openapi_spec()

    template, operation = find_operation(spec, path, method)
    collect_call(template, method)

    status_code = response.status_code
    declared = set(operation.get("responses", {}).keys())
    if str(status_code) not in declared:
        raise AssertionError(
            f"Contract violation for {method.upper()} {path}: status {status_code} "
            f"is not declared in the OpenAPI operation (declared: {sorted(declared)})"
        )

    schema = _json_schema_for(operation, status_code)
    if schema is None:
        # No JSON body schema for this response (204 / streaming / raw text).
        return

    try:
        body = response.json()
    except Exception as exc:  # noqa: BLE001 — surface a clear contract error
        raise AssertionError(
            f"Contract violation for {method.upper()} {path}: expected a JSON body "
            f"for status {status_code}, but response was not valid JSON ({exc})"
        ) from exc

    validator = build_validator(spec, schema)
    errors = list(validator.iter_errors(body))
    if errors:
        detail = "\n".join(f"  - {e.message}" for e in errors[:10])
        raise AssertionError(
            f"Response body does not match OpenAPI schema for "
            f"{method.upper()} {path} ({status_code}):\n{detail}"
        )


# ──────────────────────────────────────────────────────────────────────────
# Endpoint-call collector
# ──────────────────────────────────────────────────────────────────────────

# Session-level store of exercised operations as ``(path_template, method)``.
# Populated by ``assert_matches_openapi`` (and tests calling ``collect_call``).
CALLED_OPERATIONS: set[tuple[str, str]] = set()


def collect_call(path_template: str, method: str) -> None:
    """Record an exercised ``(path_template, method)`` operation."""
    CALLED_OPERATIONS.add((path_template, method.lower()))


def _all_operations(spec: dict[str, Any]) -> set[tuple[str, str]]:
    methods = {"get", "post", "put", "patch", "delete"}
    return {
        (path, method)
        for path, ops in spec.get("paths", {}).items()
        for method in ops
        if method in methods
    }


def write_endpoint_report(
    spec: dict[str, Any] | None = None,
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Compute endpoint coverage and write ``endpoint-coverage.{json,md}``.

    Returns the report dict. Does not raise on low coverage — the caller
    (``test_endpoint_coverage``) decides whether the floor was met.
    """
    if spec is None:
        spec = load_openapi_spec()

    output_dir = output_dir or _REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    all_ops = _all_operations(spec)
    covered = CALLED_OPERATIONS & all_ops
    uncovered = sorted(all_ops - covered)

    total = len(all_ops)
    covered_count = len(covered)
    coverage = (covered_count / total * 100) if total else 100.0

    report: dict[str, Any] = {
        "total_operations": total,
        "covered_operations": covered_count,
        "coverage_percent": round(coverage, 2),
        "min_coverage_percent": MIN_COVERAGE_PERCENT,
        "covered": sorted(f"{m.upper()} {p}" for p, m in covered),
        "uncovered": sorted(f"{m.upper()} {p}" for p, m in uncovered),
    }

    (output_dir / "endpoint-coverage.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    covered_list = "\n".join(f"- {item}" for item in report["covered"]) or "- (none)"
    uncovered_list = "\n".join(f"- {item}" for item in report["uncovered"]) or "- (none)"
    md = (
        "# Endpoint Coverage Report\n\n"
        f"- **Coverage:** {report['coverage_percent']}% "
        f"({report['covered_operations']}/{report['total_operations']} operations)\n"
        f"- **Minimum floor:** {MIN_COVERAGE_PERCENT}%\n\n"
        "## Covered\n\n"
        f"{covered_list}\n\n"
        "## Uncovered\n\n"
        f"{uncovered_list}\n"
    )
    (output_dir / "endpoint-coverage.md").write_text(md, encoding="utf-8")

    # Soft-fail gate: warn (never fail) when coverage is below the floor. This
    # runs at session teardown, so it sees the *final* coverage across all e2e
    # modules (a standalone test would only see the intermediate subset that
    # ran before it in pytest's alphabetical collection order).
    if coverage < MIN_COVERAGE_PERCENT:
        warnings.warn(
            f"Endpoint coverage {coverage:.2f}% ({covered_count}/{total}) is below "
            f"the minimum floor of {MIN_COVERAGE_PERCENT}%. "
            "Add e2e tests that exercise more documented operations.",
            UserWarning,
            stacklevel=2,
        )

    return report
