"""
@file chaos/conftest.py
@description Chaos-test fixtures: a fake external registry (dict) simulating
             the push target, plus failpoint env management. DB fixtures come
             from the root conftest (in-memory SQLite per test).
@dependencies pytest
@relatedFiles ../conftest.py, ../../app/services/sync_engine.py
"""

import pytest

from app.models.docker_image_source import DockerImageSource
from app.services import sync_engine


class FakeExternalRegistry:
    """In-memory stand-in for the external system (target registry / mirror).

    Idempotent upsert-by-key: pushing the same key with the same digest is a
    no-op; pushing a different digest is an explicit overwrite (the drift case
    reconciliation handles in Phase 3).
    """

    def __init__(self) -> None:
        self.objects: dict[str, str] = {}

    def push(self, key: str, digest: str) -> bool:
        """Upsert-by-key. Returns True when the push changed external state."""
        if self.objects.get(key) == digest:
            return False
        self.objects[key] = digest
        return True

    def get(self, key: str) -> str | None:
        return self.objects.get(key)


@pytest.fixture
def fake_registry() -> FakeExternalRegistry:
    return FakeExternalRegistry()


@pytest.fixture
def failpoint(monkeypatch):
    """Activate a failpoint for the duration of a test block."""

    def _set(spec: str | None) -> None:
        if spec is None:
            monkeypatch.delenv(sync_engine._FAILPOINT_ENV, raising=False)
        else:
            monkeypatch.setenv(sync_engine._FAILPOINT_ENV, spec)

    return _set


@pytest.fixture
async def docker_source(db_session) -> DockerImageSource:
    """Minimal docker image source with a target registry configured."""
    source = DockerImageSource(
        name="chaos-src",
        registry_url="https://registry-1.docker.io/v2",
        target_registry_url="https://harbor.local",
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source
