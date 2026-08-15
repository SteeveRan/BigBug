"""
@file test_integrity_check.py
@description Unit tests for MirrorService.check_integrity_direct() —
             direct source-vs-target commit comparison (no CI/CD).
@dependencies pytest, pytest-asyncio, unittest.mock
@relatedFiles ../../app/services/mirror.py, ../../app/models/mirror.py
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential import Credential, CredentialType
from app.models.mirror import Mirror
from app.models.pipeline import Pipeline
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.models.source_group import SourceGroup
from app.models.source_repository import SourceRepository
from app.models.sync_group import SyncGroup
from app.services.mirror import MirrorService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_integrity_chain(
    db: AsyncSession,
    source_sha: str = "abc123",
    target_project_id: str = "42",
) -> Mirror:
    """Create a full mirror chain suitable for direct integrity checking."""
    # Credential
    cred = Credential(
        name="test-cred",
        credential_type=CredentialType.github_token,
        provider="github",
        encrypted_secret="gAAAAAB...",
        status_flag=0,
    )
    db.add(cred)
    await db.flush()

    # ResourceProvider (github/external — source provider)
    github_provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.github,
        category=ProviderCategory.public,
        direction=ProviderDirection.external,
        name="test-gh-source",
        label="test-gh-source",
        credential_id=cred.id,
        verify_ssl=True,
    )
    db.add(github_provider)
    await db.flush()

    # SourceGroup
    sg = SourceGroup(
        external_id="testorg",
        name="Test Org",
        full_path="testorg",
    )
    db.add(sg)
    await db.flush()

    # SourceRepository
    sr = SourceRepository(
        provider_id=github_provider.id,
        source_group_id=sg.id,
        external_id="12345",
        name="test-repo",
        full_name="testorg/test-repo",
        clone_url_https="https://github.com/testorg/test-repo.git",
    )
    db.add(sr)
    await db.flush()

    # ResourceProvider (gitlab/system/internal)
    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.gitlab,
        category=ProviderCategory.system,
        direction=ProviderDirection.internal,
        name="test-instance",
        label="test-instance",
        base_url="https://gitlab.example.com",
        verify_ssl=True,
    )
    db.add(provider)
    await db.flush()

    # Pipeline
    pipeline = Pipeline(
        name="test-pipeline",
        provider_id=provider.id,
        ref="main",
    )
    db.add(pipeline)
    await db.flush()

    # SyncGroup
    sync_group = SyncGroup(
        name="test-sync-group",
        description="Test group",
        is_default=False,
        pipeline_id=pipeline.id,
    )
    db.add(sync_group)
    await db.flush()

    # Mirror
    mirror = Mirror(
        source_repository_id=sr.id,
        sync_group_id=sync_group.id,
        target_namespace="testns",
        target_project_name="test-repo",
        target_project_id=target_project_id,
        status_flag=0,
        status_text="OK",
    )
    db.add(mirror)
    await db.commit()
    await db.refresh(mirror)
    return mirror


# ---------------------------------------------------------------------------
# Tests: check_integrity_direct
# ---------------------------------------------------------------------------


class TestCheckIntegrityDirect:
    """Tests for MirrorService.check_integrity_direct()."""

    @pytest.mark.asyncio
    async def test_integrity_match(self, db_session: AsyncSession):
        """MATCH when source and target commits are identical."""
        mirror = await _seed_integrity_chain(db_session)

        with (
            # Phase 4: source provider resolution moved to
            # app.services.source_repository (resolve_repo_provider); the
            # target gitlab_instance token is still decrypted in mirror.py
            # (_target_gitlab_client), so both patches are needed.
            patch("app.services.source_repository.decrypt_secret", return_value="fake-token"),
            patch("app.services.mirror.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.mirror.create_source_provider",
                new_callable=AsyncMock,
            ) as mock_create,
        ):
            mock_provider = AsyncMock()
            mock_provider.get_commit_info.return_value = {
                "sha": "abc123def456",
                "date": None,
                "author": None,
            }
            mock_create.return_value = mock_provider

            with patch(
                "app.services.mirror._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class:
                mock_gl = MagicMock()
                mock_project = MagicMock()
                mock_project.default_branch = "main"
                mock_commit = MagicMock()
                mock_commit.id = "abc123def456"
                mock_project.commits.list.return_value = [mock_commit]
                mock_gl.projects.get.return_value = mock_project
                mock_gl_class.return_value = mock_gl

                result = await MirrorService.check_integrity_direct(db_session, mirror.id)

        assert result.mirror_id == mirror.id
        assert result.status == "MATCH"
        assert result.source_commit_sha == "abc123def456"
        assert result.target_commit_sha == "abc123def456"

    @pytest.mark.asyncio
    async def test_integrity_mismatch(self, db_session: AsyncSession):
        """MISMATCH when source and target commits differ."""
        mirror = await _seed_integrity_chain(db_session)

        with (
            patch("app.services.source_repository.decrypt_secret", return_value="fake-token"),
            patch("app.services.mirror.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.mirror.create_source_provider",
                new_callable=AsyncMock,
            ) as mock_create,
        ):
            mock_provider = AsyncMock()
            mock_provider.get_commit_info.return_value = {
                "sha": "abc111",
                "date": None,
                "author": None,
            }
            mock_create.return_value = mock_provider

            with patch(
                "app.services.mirror._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class:
                mock_gl = MagicMock()
                mock_project = MagicMock()
                mock_project.default_branch = "main"
                mock_commit = MagicMock()
                mock_commit.id = "xyz999"
                mock_project.commits.list.return_value = [mock_commit]
                mock_gl.projects.get.return_value = mock_project
                mock_gl_class.return_value = mock_gl

                result = await MirrorService.check_integrity_direct(db_session, mirror.id)

        assert result.status == "MISMATCH"
        assert result.source_commit_sha == "abc111"
        assert result.target_commit_sha == "xyz999"

    @pytest.mark.asyncio
    async def test_integrity_error_no_source(self, db_session: AsyncSession):
        """ERROR when source commit fetch fails."""
        mirror = await _seed_integrity_chain(db_session)

        with (
            patch("app.services.source_repository.decrypt_secret", return_value="fake-token"),
            patch("app.services.mirror.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.mirror.create_source_provider",
                new_callable=AsyncMock,
            ) as mock_create,
        ):
            mock_provider = AsyncMock()
            mock_provider.get_commit_info.side_effect = RuntimeError("API rate limit")
            mock_create.return_value = mock_provider

            result = await MirrorService.check_integrity_direct(db_session, mirror.id)

        assert result.status == "ERROR"
        assert "API rate limit" in result.message

    @pytest.mark.asyncio
    async def test_integrity_no_sync_group_raises(self, db_session: AsyncSession):
        """Raises DomainError when mirror has no SyncGroup."""
        mirror = await _seed_integrity_chain(db_session)
        # Detach from sync group
        mirror.sync_group_id = None
        await db_session.commit()

        from app.core.exceptions import DomainError

        with pytest.raises(DomainError, match="no SyncGroup"):
            await MirrorService.check_integrity_direct(db_session, mirror.id)

    @pytest.mark.asyncio
    async def test_integrity_mirror_not_found(self, db_session: AsyncSession):
        """Raises NotFoundError for non-existent mirror."""
        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await MirrorService.check_integrity_direct(db_session, 99999)

    @pytest.mark.asyncio
    async def test_integrity_creates_mirror_log(self, db_session: AsyncSession):
        """Direct integrity check creates a MirrorLog entry."""
        mirror = await _seed_integrity_chain(db_session)

        with (
            patch("app.services.source_repository.decrypt_secret", return_value="fake-token"),
            patch("app.services.mirror.decrypt_secret", return_value="fake-token"),
            patch(
                "app.services.mirror.create_source_provider",
                new_callable=AsyncMock,
            ) as mock_create,
        ):
            mock_provider = AsyncMock()
            mock_provider.get_commit_info.return_value = {
                "sha": "abc123",
                "date": None,
                "author": None,
            }
            mock_create.return_value = mock_provider

            with patch(
                "app.services.mirror._gitlab_module.Gitlab",
                autospec=True,
            ) as mock_gl_class:
                mock_gl = MagicMock()
                mock_project = MagicMock()
                mock_project.default_branch = "main"
                mock_commit = MagicMock()
                mock_commit.id = "abc123"
                mock_project.commits.list.return_value = [mock_commit]
                mock_gl.projects.get.return_value = mock_project
                mock_gl_class.return_value = mock_gl

                await MirrorService.check_integrity_direct(db_session, mirror.id)

        # Verify a MirrorLog was created
        from app.models.mirror_log import MirrorLog, MirrorLogType

        result = await db_session.execute(
            select(MirrorLog).where(
                MirrorLog.mirror_id == mirror.id,
                MirrorLog.log_type == MirrorLogType.integrity,
            )
        )
        logs = list(result.scalars().all())
        assert len(logs) >= 1
        assert logs[0].details.get("method") == "direct"
