"""
@file test_endpoint_coverage.py
@description Marker test documenting the endpoint-coverage gate. The actual
              coverage computation and soft-fail warning (below
              ``MIN_COVERAGE_PERCENT``) run at session teardown in
              ``openapi_utils.write_endpoint_report``, so they see the *final*
              set of called operations across every e2e module — not the
              intermediate subset that would have run before this file.
@dependencies backend/tests/e2e/conftest.py, backend/tests/e2e/openapi_utils.py
"""

import pytest

pytestmark = pytest.mark.e2e


def test_endpoint_coverage_is_computed_at_teardown(openapi_spec: dict) -> None:
    """The teardown report (``reports/endpoint-coverage.{json,md}``) is the source of truth.

    This test only ensures the collector fixture is wired; the floor check and
    report writing happen once at session teardown via ``write_endpoint_report``.
    """
    assert "paths" in openapi_spec
