"""
@file test_audit_mirroring.py
@description Unit tests for new audit events added as part of Git Mirroring v2
             (Этап 7.1). Covers credential, source_provider, source_group,
             pipeline, mirror sync/freshness/integrity completion events.
@dependencies pytest, pytest-asyncio, httpx, backend/tests/conftest.py,
              app.services.audit.AuditService
@relatedFiles ../../app/api/credentials.py, ../../app/api/mirroring.py,
               ../../app/api/pipelines.py, ../../app/api/webhooks.py,
               ../../app/services/mirror.py
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.secrets import encrypt_secret
from app.models.credential import Credential, CredentialType
from app.models.gitlab_instance import GitlabInstance
from app.models.mirror import Mirror
from app.models.mirror_log import MirrorLog, MirrorLogType
from app.models.pipeline import Pipeline
from app.models.pipeline_run import PipelineRun
from app.models.source_group import SourceGroup
from app.models.source_provider import SourceProvider
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.schemas.credential import CredentialOut
from app.schemas.source_group import SourceGroupDetailOut, SourceGroupListOut
from app.schemas.source_provider import SourceProviderOut
from app.schemas.source_repository import SourceRepositoryListOut
from app.services.mirror import MirrorService

# Ensure forward references are resolved for Pydantic v2 before any schema usage.
# Namespace must be passed explicitly because schema modules only import
# cross-referenced types under TYPE_CHECKING (not available at runtime).
SourceProviderOut.model_rebuild(_types_namespace={"CredentialOut": CredentialOut})
SourceGroupListOut.model_rebuild()
SourceGroupDetailOut.model_rebuild(
    _types_namespace={
        "SourceProviderOut": SourceProviderOut,
        "SourceRepositoryListOut": SourceRepositoryListOut,
    }
)


# ── Helpers ─────────────────────────────────────────────────────────


async def _seed_credential(db: AsyncSession) -> Credential:
    """Create a non-deleted test credential with a valid Fernet-encrypted secret."""
    cred = Credential(
        name="test-token",
        credential_type=CredentialType.github_token,
        provider="github",
        username="testuser",
        encrypted_secret=encrypt_secret("ghp_test_audit_mirroring_token"),
        status_flag=0,
        status_text="OK",
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)
    return cred


async def _seed_source_provider(db: AsyncSession) -> SourceProvider:
    """Create a test source provider with credential."""
    cred = await _seed_credential(db)
    sp = SourceProvider(
        credential_id=cred.id,
        provider_type="github",
        label="test-provider",
    )
    db.add(sp)
    await db.commit()
    await db.refresh(sp)
    return sp


async def _seed_source_group(db: AsyncSession) -> SourceGroup:
    """Create a test source group."""
    sp = await _seed_source_provider(db)
    sg = SourceGroup(
        external_id="test-org",
        name="test-org",
        full_path="https://github.com/test-org",
    )
    db.add(sg)
    await db.commit()
    await db.refresh(sg)
    return sg


async def _seed_source_repo(db: AsyncSession) -> SourceRepository:
    """Create a test source repository (with eager-loaded source_provider)."""
    sg = await _seed_source_group(db)
    sp = await _seed_source_provider(db)
    sr = SourceRepository(
        source_provider_id=sp.id,
        source_group_id=sg.id,
        external_id="test/repo",
        name="repo",
        full_name="test/repo",
        clone_url_https="https://github.com/test/repo.git",
    )
    db.add(sr)
    await db.commit()
    # Eager-load relationships to avoid MissingGreenlet in service-layer tests
    result = await db.execute(
        select(SourceRepository)
        .options(
            selectinload(SourceRepository.source_group),
            selectinload(SourceRepository.source_provider),
        )
        .where(SourceRepository.id == sr.id)
    )
    return result.scalar_one()


async def _seed_mirror(db: AsyncSession) -> Mirror:
    """Create a test mirror with sync_group, pipeline and gitlab_instance (eager-loaded)."""
    sr = await _seed_source_repo(db)

    # Create a GitLab instance (required by Pipeline for trigger_pipeline)
    gitlab_instance = GitlabInstance(
        name="test-gitlab",
        url="https://gitlab.example.com",
        is_default=True,
    )
    db.add(gitlab_instance)
    await db.flush()

    # Create a pipeline linked to the GitLab instance
    pipeline = Pipeline(
        name="test-pipeline",
        ref="main",
        is_default=False,
        is_enabled=True,
        gitlab_instance_id=gitlab_instance.id,
    )
    db.add(pipeline)
    await db.flush()

    # Create a SyncGroup
    sync_group = SyncGroup(
        name="test-sync-group",
        pipeline_id=pipeline.id,
        is_default=True,
    )
    db.add(sync_group)
    await db.flush()

    mirror = Mirror(
        source_repository_id=sr.id,
        sync_group_id=sync_group.id,
        target_namespace="test-ns",
        target_project_name="test-project",
        target_project_id="12345",
        status_flag=0,
        status_text="OK",
    )
    db.add(mirror)
    await db.commit()

    # Eager-load the mirror with ALL relationships (matches _get_mirror_or_404)
    result = await db.execute(
        select(Mirror)
        .options(
            selectinload(Mirror.source_repository)
            .selectinload(SourceRepository.source_group),
            selectinload(Mirror.source_repository)
            .selectinload(SourceRepository.source_provider),
            selectinload(Mirror.sync_group)
            .selectinload(SyncGroup.pipeline)
            .selectinload(Pipeline.gitlab_instance),
        )
        .where(Mirror.id == mirror.id)
    )
    return result.scalar_one()


def _find_audit_action(mock_audit, action: str) -> bool:
    """Check if mock_audit received a call with the given action."""
    for call_args in mock_audit.call_args_list:
        kwargs_action = call_args.kwargs.get("action")
        args_action = call_args.args[1] if len(call_args.args) >= 2 else None
        if kwargs_action == action or args_action == action:
            return True
    return False


# ── Credential Audit Events ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_credential_created_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """POST /api/credentials/ should log credential.created audit event."""
    with patch("app.api.credentials.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.post(
            "/api/credentials/",
            json={
                "name": "audit-test-token",
                "credential_type": "github_token",
                "provider": "github",
                "username": "testuser",
                "secret": "ghp_test123456789",
            },
            headers=login_headers,
        )

    assert response.status_code == 201
    assert _find_audit_action(mock_audit, "credential.created"), (
        "Expected credential.created audit event"
    )


@pytest.mark.asyncio
async def test_credential_updated_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """PATCH /api/credentials/{id} should log credential.updated audit event."""
    cred = await _seed_credential(db_session)

    with patch("app.api.credentials.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.patch(
            f"/api/credentials/{cred.id}",
            json={"name": "updated-token-name"},
            headers=login_headers,
        )

    assert response.status_code == 200
    assert _find_audit_action(mock_audit, "credential.updated"), (
        "Expected credential.updated audit event"
    )


@pytest.mark.asyncio
async def test_credential_deleted_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """DELETE /api/credentials/{id} should log credential.deleted audit event."""
    cred = await _seed_credential(db_session)

    with patch("app.api.credentials.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.delete(
            f"/api/credentials/{cred.id}",
            headers=login_headers,
        )

    assert response.status_code == 204
    assert _find_audit_action(mock_audit, "credential.deleted"), (
        "Expected credential.deleted audit event"
    )


@pytest.mark.asyncio
async def test_credential_tested_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """POST /api/credentials/{id}/test should log credential.tested audit event."""
    cred = await _seed_credential(db_session)

    with patch("app.api.credentials.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.post(
            f"/api/credentials/{cred.id}/test",
            headers=login_headers,
        )

    assert response.status_code == 200
    assert _find_audit_action(mock_audit, "credential.tested"), (
        "Expected credential.tested audit event"
    )


# ── Source Provider Audit Events ────────────────────────────────────


@pytest.mark.asyncio
async def test_source_provider_created_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """POST /api/mirroring/providers/ should log source_provider.created audit event."""
    cred = await _seed_credential(db_session)

    with patch("app.api.mirroring.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.post(
            "/api/mirroring/providers/",
            json={
                "credential_id": cred.id,
                "provider_type": "github",
                "label": "audit-test-provider",
            },
            headers=login_headers,
        )

    assert response.status_code == 201
    assert _find_audit_action(mock_audit, "source_provider.created"), (
        "Expected source_provider.created audit event"
    )


# ── Source Group Audit Events ───────────────────────────────────────


@pytest.mark.asyncio
async def test_source_group_refreshed_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """POST /api/mirroring/groups/{id}/refresh should log source_group.refreshed audit event."""
    sg = await _seed_source_group(db_session)

    with (
        patch("app.api.mirroring.AuditService.log_event", new_callable=AsyncMock) as mock_audit,
        patch(
            "app.services.source_providers.create_source_provider", new_callable=AsyncMock
        ) as mock_factory,
    ):
        # Mock the GitHub provider to return empty repos (otherwise it will try real API)
        mock_provider = AsyncMock()
        mock_provider.list_repositories = AsyncMock(return_value=[])
        mock_factory.return_value = mock_provider

        response = await client.post(
            f"/api/mirroring/groups/{sg.id}/refresh",
            headers=login_headers,
        )

    assert response.status_code == 200
    assert _find_audit_action(mock_audit, "source_group.refreshed"), (
        "Expected source_group.refreshed audit event"
    )


# ── Pipeline Config Audit Events ────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_created_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """POST /api/pipelines/configs should log pipeline.created audit event."""
    with patch("app.api.pipelines.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.post(
            "/api/pipelines/configs",
            json={
                "name": "audit-test-pipeline",
                "ref": "main",
                "is_enabled": True,
            },
            headers=login_headers,
        )

    assert response.status_code == 201
    assert _find_audit_action(mock_audit, "pipeline.created"), (
        "Expected pipeline.created audit event"
    )


@pytest.mark.asyncio
async def test_pipeline_updated_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """PATCH /api/pipelines/configs/{id} should log pipeline.updated audit event."""
    # Create a pipeline first
    pipeline = Pipeline(name="to-update", ref="main", is_enabled=True)
    db_session.add(pipeline)
    await db_session.commit()
    await db_session.refresh(pipeline)

    with patch("app.api.pipelines.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.patch(
            f"/api/pipelines/configs/{pipeline.id}",
            json={"name": "updated-pipeline"},
            headers=login_headers,
        )

    assert response.status_code == 200
    assert _find_audit_action(mock_audit, "pipeline.updated"), (
        "Expected pipeline.updated audit event"
    )


@pytest.mark.asyncio
async def test_pipeline_deleted_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """DELETE /api/pipelines/configs/{id} should log pipeline.deleted audit event."""
    pipeline = Pipeline(name="to-delete", ref="main", is_enabled=True)
    db_session.add(pipeline)
    await db_session.commit()
    await db_session.refresh(pipeline)

    with patch("app.api.pipelines.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.delete(
            f"/api/pipelines/configs/{pipeline.id}",
            headers=login_headers,
        )

    assert response.status_code == 204
    assert _find_audit_action(mock_audit, "pipeline.deleted"), (
        "Expected pipeline.deleted audit event"
    )


@pytest.mark.asyncio
async def test_pipeline_duplicated_audit(
    db_session: AsyncSession, client: AsyncClient, login_headers: dict
):
    """POST /api/pipelines/configs/{id}/duplicate should log pipeline.duplicated audit event."""
    pipeline = Pipeline(name="to-duplicate", ref="main", is_enabled=True)
    db_session.add(pipeline)
    await db_session.commit()
    await db_session.refresh(pipeline)

    with patch("app.api.pipelines.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.post(
            f"/api/pipelines/configs/{pipeline.id}/duplicate",
            json={"name": "duplicated-pipeline"},
            headers=login_headers,
        )

    assert response.status_code == 200
    assert _find_audit_action(mock_audit, "pipeline.duplicated"), (
        "Expected pipeline.duplicated audit event"
    )


# ── Mirror Freshness & Integrity Completion Audit Events ────────────


@pytest.mark.asyncio
async def test_mirror_freshness_checked_audit(db_session: AsyncSession):
    """check_freshness() should log mirror.freshness_checked after mirror.freshness_triggered."""
    mirror = await _seed_mirror(db_session)

    with (
        patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock) as mock_audit,
        patch("app.services.mirror.create_source_provider", new_callable=AsyncMock) as mock_factory,
    ):
        mock_provider = AsyncMock()
        mock_provider.get_commit_info = AsyncMock(
            return_value={
                "sha": "abc123def456",
                "date": datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
                "author": "test",
                "message": "feat: add feature",
            }
        )
        mock_factory.return_value = mock_provider

        result = await MirrorService.check_freshness(db_session, mirror.id, username="testuser")

    assert isinstance(result, MirrorLog)
    assert _find_audit_action(mock_audit, "mirror.freshness_triggered"), (
        "Expected mirror.freshness_triggered audit event"
    )
    assert _find_audit_action(mock_audit, "mirror.freshness_checked"), (
        "Expected mirror.freshness_checked audit event"
    )


@pytest.mark.asyncio
async def test_mirror_integrity_checked_audit(db_session: AsyncSession):
    """check_integrity() should log mirror.integrity_checked after mirror.integrity_triggered."""
    mirror = await _seed_mirror(db_session)

    with (
        patch("app.services.mirror.AuditService.log_event", new_callable=AsyncMock) as mock_audit,
        patch("app.services.mirror.trigger_pipeline", new_callable=AsyncMock) as mock_trigger,
    ):
        # Mock trigger_pipeline to return a PipelineRun
        mock_run = PipelineRun(
            id=999,
            gitlab_instance_id=mirror.sync_group.pipeline.gitlab_instance_id,
            gitlab_project_id=12345,
            gitlab_pipeline_id=100,
            ref="main",
            status_flag=3,
            status_text="Running",
        )
        mock_trigger.return_value = mock_run

        await MirrorService.check_integrity(db_session, mirror.id, user_id=1, username="testuser")

    assert _find_audit_action(mock_audit, "mirror.integrity_triggered"), (
        "Expected mirror.integrity_triggered audit event"
    )
    assert _find_audit_action(mock_audit, "mirror.integrity_checked"), (
        "Expected mirror.integrity_checked audit event"
    )


# ── Mirror Sync Completion (Webhook) Audit Events ──────────────────


@pytest.mark.asyncio
async def test_mirror_sync_completed_audit(db_session: AsyncSession, client: AsyncClient):
    """Webhook handling of a successful pipeline should log mirror.sync_completed."""
    mirror = await _seed_mirror(db_session)

    # Create a PipelineRun associated with a MirrorLog
    pipeline_run = PipelineRun(
        gitlab_instance_id=1,
        gitlab_project_id=12345,
        gitlab_pipeline_id=200,
        ref="main",
        status_flag=3,
        status_text="Running",
        triggered_by_user_id=1,
    )
    db_session.add(pipeline_run)
    await db_session.flush()

    mirror_log = MirrorLog(
        mirror_id=mirror.id,
        pipeline_run_id=pipeline_run.id,
        log_type=MirrorLogType.sync,
        status_flag=3,
        status_text="Running",
        triggered_by="testuser",
    )
    db_session.add(mirror_log)
    await db_session.commit()

    with patch("app.api.webhooks.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.post(
            "/api/webhooks/gitlab",
            json={
                "object_kind": "pipeline",
                "object_attributes": {
                    "id": pipeline_run.gitlab_pipeline_id,
                    "status": "success",
                    "duration": 120,
                },
                "project": {"web_url": "http://gitlab.example.com/test/test-project"},
            },
        )

    assert response.status_code == 200
    assert _find_audit_action(mock_audit, "mirror.sync_completed"), (
        "Expected mirror.sync_completed audit event"
    )


@pytest.mark.asyncio
async def test_mirror_sync_failed_audit(db_session: AsyncSession, client: AsyncClient):
    """Webhook handling of a failed pipeline should log mirror.sync_failed."""
    mirror = await _seed_mirror(db_session)

    pipeline_run = PipelineRun(
        gitlab_instance_id=1,
        gitlab_project_id=12345,
        gitlab_pipeline_id=300,
        ref="main",
        status_flag=3,
        status_text="Running",
        triggered_by_user_id=1,
    )
    db_session.add(pipeline_run)
    await db_session.flush()

    mirror_log = MirrorLog(
        mirror_id=mirror.id,
        pipeline_run_id=pipeline_run.id,
        log_type=MirrorLogType.sync,
        status_flag=3,
        status_text="Running",
        triggered_by="testuser",
    )
    db_session.add(mirror_log)
    await db_session.commit()

    with patch("app.api.webhooks.AuditService.log_event", new_callable=AsyncMock) as mock_audit:
        response = await client.post(
            "/api/webhooks/gitlab",
            json={
                "object_kind": "pipeline",
                "object_attributes": {
                    "id": pipeline_run.gitlab_pipeline_id,
                    "status": "failed",
                    "duration": 60,
                },
                "project": {"web_url": "http://gitlab.example.com/test/test-project"},
            },
        )

    assert response.status_code == 200
    assert _find_audit_action(mock_audit, "mirror.sync_failed"), (
        "Expected mirror.sync_failed audit event"
    )
