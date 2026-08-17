"""
@file test_webhooks.py
@description E2E tests for the GitLab webhook endpoint (/api/webhooks/gitlab)
              against a live backend. Only non-pipeline events are exercised,
              which the handler acknowledges with 200 without touching GitLab.
              No mocks, no sqlite.
@dependencies backend/tests/e2e/conftest.py
"""

import pytest
from httpx import AsyncClient

from tests.e2e.conftest import assert_matches_openapi

pytestmark = pytest.mark.e2e


class TestGitLabWebhook:
    async def test_gitlab_webhook_ignored_200(self, client: AsyncClient, openapi_spec: dict):
        response = await client.post("/api/webhooks/gitlab", json={"object_kind": "issue"})
        assert_matches_openapi(response, "/api/webhooks/gitlab", "post", openapi_spec)
        assert response.status_code == 200
