"""
@file test_reconciliation_service.py
@description Unit tests for the reconciliation service pass (issue #111):
              a manually drifted mirror (tag deleted in the target registry)
              is detected, repaired via idempotent re-push, and reported
              into the outbox. Uses a fake registry client — no network.
@dependencies pytest, unittest.mock, sqlalchemy
@relatedFiles ../../app/services/reconciliation.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.docker_image_source import DockerImageSource
from app.models.docker_image_tag import DockerImageTag
from app.models.notification_outbox import NotificationOutbox
from app.services.reconciliation import reconcile_docker_source


class FakeRegistryClient:
    """In-memory stand-in for DockerRegistryClient (tags/list view)."""

    def __init__(self, tags: dict[str, list[str]]):
        self.tags = tags
        self.pushes: list[str] = []

    async def list_tags(self, repository: str) -> list[str]:
        return list(self.tags.get(repository, []))


async def _seed_source_with_synced_tag(db_session) -> tuple[DockerImageSource, DockerImageTag]:
    source = DockerImageSource(
        name="reconcile-src",
        registry_url="https://registry-1.docker.io/v2",
        target_registry_url="https://harbor.local",
        target_project="bigbug",
    )
    db_session.add(source)
    await db_session.flush()

    tag_row = DockerImageTag(
        source_id=source.id,
        image_name="library/nginx",
        tag="latest",
        digest="sha256:aaa",
        is_synced=True,
        status_flag=0,
    )
    db_session.add(tag_row)
    await db_session.commit()
    return source, tag_row


@pytest.mark.asyncio
async def test_drift_detected_repaired_and_reported(db_session):
    """Tag deleted in the target registry (GC / manual rebuild):
    reconcile detects it, repairs via re-push, writes one outbox event."""
    source, _tag = await _seed_source_with_synced_tag(db_session)

    client = FakeRegistryClient({"bigbug/nginx": []})  # tag GONE
    pushes: list[tuple] = []

    with (
        patch(
            "app.services.reconciliation._target_client",
            new_callable=AsyncMock,
            return_value=(client, "harbor.local"),
        ),
        patch("app.services.docker.docker_service.sync_image", new_callable=AsyncMock) as mock_sync,
    ):
        # Repair goes through docker_service.sync_image (idempotent crane copy).
        mock_sync.side_effect = lambda source, image, tag, db, triggered_by: (
            pushes.append((image, tag, triggered_by)) or MagicMock(status_flag=0)
        )
        summary = await reconcile_docker_source(db_session, source.id)

    assert summary["checked"] == 1
    assert summary["missing"] == 1
    assert summary["repaired"] == 1
    assert pushes == [("library/nginx", "latest", "reconcile")]

    rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
    assert len(rows) == 1
    assert rows[0].event_type == "reconciliation.drift"
    assert rows[0].payload["repository"] == "bigbug/nginx"
    assert rows[0].payload["tag"] == "latest"
    assert rows[0].sent_at is None


@pytest.mark.asyncio
async def test_no_drift_no_outbox_event(db_session):
    """Converged tag: no repair, no outbox event."""
    source, _tag = await _seed_source_with_synced_tag(db_session)
    client = FakeRegistryClient({"bigbug/nginx": ["latest"]})

    with (
        patch(
            "app.services.reconciliation._target_client",
            new_callable=AsyncMock,
            return_value=(client, "harbor.local"),
        ),
        patch("app.services.docker.docker_service.sync_image", new_callable=AsyncMock),
    ):
        summary = await reconcile_docker_source(db_session, source.id)

    assert summary == {
        "source_id": source.id,
        "checked": 1,
        "missing": 0,
        "repaired": 0,
        "failed": 0,
    }
    rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_outbox_event_dedup_on_second_pass(db_session):
    """Second reconcile pass for the same drift (cron + manual): the dedup
    key collapses to one outbox row."""
    source, _tag = await _seed_source_with_synced_tag(db_session)
    client = FakeRegistryClient({"bigbug/nginx": []})

    def _fake_sync(source, image, tag, db, triggered_by):
        return MagicMock(status_flag=0)

    with (
        patch(
            "app.services.reconciliation._target_client",
            new_callable=AsyncMock,
            return_value=(client, "harbor.local"),
        ),
        patch("app.services.docker.docker_service.sync_image", side_effect=_fake_sync),
    ):
        await reconcile_docker_source(db_session, source.id)
        await reconcile_docker_source(db_session, source.id)

    rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_registry_error_counted_not_raised(db_session):
    """tags/list failure on one source doesn't crash the pass — counted as failed."""
    source, _tag = await _seed_source_with_synced_tag(db_session)

    from app.services.providers.clients._http import ProviderClientError

    class FailingClient:
        async def list_tags(self, repository: str) -> list[str]:
            raise ProviderClientError("HTTP 503", status_code=503)

    with patch(
        "app.services.reconciliation._target_client",
        new_callable=AsyncMock,
        return_value=(FailingClient(), "harbor.local"),
    ):
        summary = await reconcile_docker_source(db_session, source.id)

    assert summary["failed"] == 1
    assert summary["repaired"] == 0
