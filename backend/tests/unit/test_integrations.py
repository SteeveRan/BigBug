"""
@file test_integrations.py
@description Unit tests for integration instance services:
             GitlabInstanceService, HarborInstanceService, GithubInstanceService,
             DockerRegistryInstanceService, HelmRepositoryInstanceService.
             50 tests total — 10 per integration type.
@dependencies pytest, pytest-asyncio, unittest.mock, backend/tests/conftest.py
@relatedFiles ../app/services/integrations.py, ../app/models/
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.secrets import decrypt_secret
from app.services.integrations import (
    DockerRegistryInstanceService,
    GithubInstanceService,
    GitlabInstanceService,
    HarborInstanceService,
    HelmRepositoryInstanceService,
)

# ═══════════════════════════════════════════════════════════════════════════════
# GitLab Instance Service Tests (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGitlabInstanceService:
    """Unit tests for GitlabInstanceService CRUD and connection testing."""

    # ── list_instances ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_gitlab_instances(self, db_session: AsyncSession):
        """Create 2 instances, then verify list returns both."""
        svc = GitlabInstanceService(db_session)
        await svc.create_instance(
            name="gitlab-prod", url="https://gitlab.prod.example.com", token="tok1"
        )
        await svc.create_instance(
            name="gitlab-staging", url="https://gitlab.staging.example.com", token="tok2"
        )

        result = await svc.list_instances()
        assert len(result) == 2
        names = {r.name for r in result}
        assert names == {"gitlab-prod", "gitlab-staging"}

    # ── get_instance ───────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_gitlab_instance(self, db_session: AsyncSession):
        """Create an instance then retrieve it by ID."""
        svc = GitlabInstanceService(db_session)
        created = await svc.create_instance(
            name="gitlab-get", url="https://gitlab.example.com", token="mytoken"
        )
        fetched = await svc.get_instance(created.id)
        assert fetched.id == created.id
        assert fetched.name == "gitlab-get"
        assert fetched.url == "https://gitlab.example.com"

    @pytest.mark.asyncio
    async def test_get_gitlab_instance_not_found(self, db_session: AsyncSession):
        """Retrieving a non-existent ID raises NotFoundError."""
        svc = GitlabInstanceService(db_session)
        with pytest.raises(NotFoundError) as exc_info:
            await svc.get_instance(99999)
        assert "id=99999" in str(exc_info.value.detail)

    # ── create_instance ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_create_gitlab_instance(self, db_session: AsyncSession):
        """Create an instance and verify token is encrypted (not plaintext)."""
        svc = GitlabInstanceService(db_session)
        instance = await svc.create_instance(
            name="gitlab-enc", url="https://gitlab.example.com", token="super-secret-token"
        )
        assert instance.id is not None
        assert instance.name == "gitlab-enc"
        assert instance.url == "https://gitlab.example.com"
        # Token must be encrypted at rest
        assert instance.token != "super-secret-token"
        assert decrypt_secret(instance.token) == "super-secret-token"
        assert instance.status_flag == 4  # STATUS_PENDING
        assert instance.status_text == "Pending"

    @pytest.mark.asyncio
    async def test_create_gitlab_instance_duplicate_name(self, db_session: AsyncSession):
        """Creating an instance with the same name raises ConflictError."""
        svc = GitlabInstanceService(db_session)
        await svc.create_instance(
            name="gitlab-dup", url="https://gitlab1.example.com", token="tok1"
        )
        with pytest.raises(ConflictError) as exc_info:
            await svc.create_instance(
                name="gitlab-dup", url="https://gitlab2.example.com", token="tok2"
            )
        assert "already exists" in str(exc_info.value.detail)

    # ── update_instance ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_update_gitlab_instance(self, db_session: AsyncSession):
        """Update name and URL of an existing instance."""
        svc = GitlabInstanceService(db_session)
        created = await svc.create_instance(
            name="gitlab-old", url="https://old.example.com", token="tok"
        )
        updated = await svc.update_instance(
            created.id, name="gitlab-new", url="https://new.example.com"
        )
        assert updated.name == "gitlab-new"
        assert updated.url == "https://new.example.com"

    @pytest.mark.asyncio
    async def test_update_gitlab_instance_token(self, db_session: AsyncSession):
        """Update token and verify re-encryption with a different ciphertext."""
        svc = GitlabInstanceService(db_session)
        created = await svc.create_instance(
            name="gitlab-rekey", url="https://gitlab.example.com", token="old-token"
        )
        old_ciphertext = created.token

        updated = await svc.update_instance(created.id, token="new-token")
        # Ciphertext must change after re-encryption (different plaintext → different ciphertext)
        assert updated.token != old_ciphertext
        assert decrypt_secret(updated.token) == "new-token"

    # ── delete_instance ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_delete_gitlab_instance(self, db_session: AsyncSession):
        """Delete an instance and verify it's gone."""
        svc = GitlabInstanceService(db_session)
        created = await svc.create_instance(
            name="gitlab-del", url="https://gitlab.example.com", token="tok"
        )
        await svc.delete_instance(created.id)
        with pytest.raises(NotFoundError):
            await svc.get_instance(created.id)

    # ── test_connection ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_gitlab_test_connection_success(self, db_session: AsyncSession):
        """Mock httpx to simulate a successful GitLab /api/v4/version response."""
        svc = GitlabInstanceService(db_session)
        instance = await svc.create_instance(
            name="gitlab-conn-ok", url="https://gitlab.example.com", token="valid-token"
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"version": "16.8.0-ee", "revision": "abc123"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await svc.test_connection(instance.id)

        assert result["success"] is True
        assert "Connected" in result["message"]
        assert "16.8.0" in result["message"]
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_gitlab_test_connection_failure(self, db_session: AsyncSession):
        """Mock httpx to simulate a connection error to GitLab."""
        svc = GitlabInstanceService(db_session)
        instance = await svc.create_instance(
            name="gitlab-conn-fail", url="https://gitlab-down.example.com", token="tok"
        )

        # Simulate a network-level error (httpx.ConnectError)
        import httpx

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            result = await svc.test_connection(instance.id)

        assert result["success"] is False
        assert "Could not reach" in result["message"]
        assert result["status_code"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Harbor Instance Service Tests (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHarborInstanceService:
    """Unit tests for HarborInstanceService CRUD and connection testing."""

    @pytest.mark.asyncio
    async def test_list_harbor_instances(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        await svc.create_instance(
            name="harbor-prod",
            url="https://harbor.prod.example.com",
            username="admin",
            password="pass1",
        )
        await svc.create_instance(
            name="harbor-staging",
            url="https://harbor.staging.example.com",
            username="admin",
            password="pass2",
        )
        result = await svc.list_instances()
        assert len(result) == 2
        names = {r.name for r in result}
        assert names == {"harbor-prod", "harbor-staging"}

    @pytest.mark.asyncio
    async def test_get_harbor_instance(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        created = await svc.create_instance(
            name="harbor-get", url="https://harbor.example.com", username="admin", password="secret"
        )
        fetched = await svc.get_instance(created.id)
        assert fetched.name == "harbor-get"
        assert fetched.username == "admin"

    @pytest.mark.asyncio
    async def test_get_harbor_instance_not_found(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        with pytest.raises(NotFoundError):
            await svc.get_instance(99999)

    @pytest.mark.asyncio
    async def test_create_harbor_instance(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        instance = await svc.create_instance(
            name="harbor-enc",
            url="https://harbor.example.com",
            username="admin",
            password="super-secret",
        )
        assert instance.password != "super-secret"
        assert decrypt_secret(instance.password) == "super-secret"
        assert instance.status_flag == 4  # STATUS_PENDING

    @pytest.mark.asyncio
    async def test_create_harbor_instance_duplicate_name(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        await svc.create_instance(
            name="harbor-dup", url="https://harbor1.example.com", username="admin", password="pass1"
        )
        with pytest.raises(ConflictError):
            await svc.create_instance(
                name="harbor-dup",
                url="https://harbor2.example.com",
                username="admin",
                password="pass2",
            )

    @pytest.mark.asyncio
    async def test_update_harbor_instance(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        created = await svc.create_instance(
            name="harbor-old", url="https://old.example.com", username="admin", password="pass"
        )
        updated = await svc.update_instance(
            created.id, name="harbor-new", url="https://new.example.com"
        )
        assert updated.name == "harbor-new"
        assert updated.url == "https://new.example.com"

    @pytest.mark.asyncio
    async def test_update_harbor_instance_password(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        created = await svc.create_instance(
            name="harbor-rekey",
            url="https://harbor.example.com",
            username="admin",
            password="old-pass",
        )
        old_ciphertext = created.password
        updated = await svc.update_instance(created.id, password="new-pass")
        assert updated.password != old_ciphertext
        assert decrypt_secret(updated.password) == "new-pass"

    @pytest.mark.asyncio
    async def test_delete_harbor_instance(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        created = await svc.create_instance(
            name="harbor-del", url="https://harbor.example.com", username="admin", password="pass"
        )
        await svc.delete_instance(created.id)
        with pytest.raises(NotFoundError):
            await svc.get_instance(created.id)

    @pytest.mark.asyncio
    async def test_harbor_test_connection_success(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        instance = await svc.create_instance(
            name="harbor-conn-ok",
            url="https://harbor.example.com",
            username="admin",
            password="valid-pass",
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await svc.test_connection(instance.id)

        assert result["success"] is True
        assert "Connected" in result["message"]
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_harbor_test_connection_failure(self, db_session: AsyncSession):
        svc = HarborInstanceService(db_session)
        instance = await svc.create_instance(
            name="harbor-conn-fail",
            url="https://harbor-down.example.com",
            username="admin",
            password="pass",
        )
        import httpx

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            result = await svc.test_connection(instance.id)
        assert result["success"] is False
        assert "Could not reach" in result["message"]


# ═══════════════════════════════════════════════════════════════════════════════
# GitHub Instance Service Tests (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGithubInstanceService:
    """Unit tests for GithubInstanceService CRUD and connection testing."""

    @pytest.mark.asyncio
    async def test_list_github_instances(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        await svc.create_instance(name="github-org1", token="tok1")
        await svc.create_instance(name="github-org2", token="tok2")
        result = await svc.list_instances()
        assert len(result) == 2
        names = {r.name for r in result}
        assert names == {"github-org1", "github-org2"}

    @pytest.mark.asyncio
    async def test_get_github_instance(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        created = await svc.create_instance(name="github-get", token="mytoken")
        fetched = await svc.get_instance(created.id)
        assert fetched.name == "github-get"

    @pytest.mark.asyncio
    async def test_get_github_instance_not_found(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        with pytest.raises(NotFoundError):
            await svc.get_instance(99999)

    @pytest.mark.asyncio
    async def test_create_github_instance(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        instance = await svc.create_instance(name="github-enc", token="super-secret-token")
        assert instance.token != "super-secret-token"
        assert decrypt_secret(instance.token) == "super-secret-token"
        assert instance.status_flag == 4

    @pytest.mark.asyncio
    async def test_create_github_instance_duplicate_name(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        await svc.create_instance(name="github-dup", token="tok1")
        with pytest.raises(ConflictError):
            await svc.create_instance(name="github-dup", token="tok2")

    @pytest.mark.asyncio
    async def test_update_github_instance(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        created = await svc.create_instance(name="github-old", token="tok")
        updated = await svc.update_instance(created.id, name="github-new")
        assert updated.name == "github-new"

    @pytest.mark.asyncio
    async def test_update_github_instance_token(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        created = await svc.create_instance(name="github-rekey", token="old-tok")
        old_ciphertext = created.token
        updated = await svc.update_instance(created.id, token="new-tok")
        assert updated.token != old_ciphertext
        assert decrypt_secret(updated.token) == "new-tok"

    @pytest.mark.asyncio
    async def test_delete_github_instance(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        created = await svc.create_instance(name="github-del", token="tok")
        await svc.delete_instance(created.id)
        with pytest.raises(NotFoundError):
            await svc.get_instance(created.id)

    @pytest.mark.asyncio
    async def test_github_test_connection_success(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        instance = await svc.create_instance(name="github-conn-ok", token="valid-token")

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"login": "test-user"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await svc.test_connection(instance.id)

        assert result["success"] is True
        assert "test-user" in result["message"]
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_github_test_connection_failure(self, db_session: AsyncSession):
        svc = GithubInstanceService(db_session)
        instance = await svc.create_instance(name="github-conn-fail", token="bad-tok")
        import httpx

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            result = await svc.test_connection(instance.id)
        assert result["success"] is False
        assert "Could not reach" in result["message"]


# ═══════════════════════════════════════════════════════════════════════════════
# Docker Registry Instance Service Tests (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDockerRegistryInstanceService:
    """Unit tests for DockerRegistryInstanceService CRUD and connection testing."""

    @pytest.mark.asyncio
    async def test_list_docker_registry_instances(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        await svc.create_instance(
            name="dr-prod",
            url="https://registry.prod.example.com",
            username="user",
            password="pass1",
        )
        await svc.create_instance(
            name="dr-staging",
            url="https://registry.staging.example.com",
            username="user",
            password="pass2",
        )
        result = await svc.list_instances()
        assert len(result) == 2
        names = {r.name for r in result}
        assert names == {"dr-prod", "dr-staging"}

    @pytest.mark.asyncio
    async def test_get_docker_registry_instance(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        created = await svc.create_instance(
            name="dr-get", url="https://registry.example.com", username="user", password="secret"
        )
        fetched = await svc.get_instance(created.id)
        assert fetched.name == "dr-get"
        assert fetched.username == "user"

    @pytest.mark.asyncio
    async def test_get_docker_registry_instance_not_found(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        with pytest.raises(NotFoundError):
            await svc.get_instance(99999)

    @pytest.mark.asyncio
    async def test_create_docker_registry_instance(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        instance = await svc.create_instance(
            name="dr-enc",
            url="https://registry.example.com",
            username="user",
            password="super-secret",
        )
        assert instance.password != "super-secret"
        assert decrypt_secret(instance.password) == "super-secret"
        assert instance.status_flag == 4

    @pytest.mark.asyncio
    async def test_create_docker_registry_instance_duplicate_name(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        await svc.create_instance(
            name="dr-dup", url="https://reg1.example.com", username="user", password="pass1"
        )
        with pytest.raises(ConflictError):
            await svc.create_instance(
                name="dr-dup", url="https://reg2.example.com", username="user", password="pass2"
            )

    @pytest.mark.asyncio
    async def test_update_docker_registry_instance(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        created = await svc.create_instance(
            name="dr-old", url="https://old.example.com", username="user", password="pass"
        )
        updated = await svc.update_instance(
            created.id, name="dr-new", url="https://new.example.com"
        )
        assert updated.name == "dr-new"
        assert updated.url == "https://new.example.com"

    @pytest.mark.asyncio
    async def test_update_docker_registry_instance_password(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        created = await svc.create_instance(
            name="dr-rekey",
            url="https://registry.example.com",
            username="user",
            password="old-pass",
        )
        old_ciphertext = created.password
        updated = await svc.update_instance(created.id, password="new-pass")
        assert updated.password != old_ciphertext
        assert decrypt_secret(updated.password) == "new-pass"

    @pytest.mark.asyncio
    async def test_delete_docker_registry_instance(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        created = await svc.create_instance(
            name="dr-del", url="https://registry.example.com", username="user", password="pass"
        )
        await svc.delete_instance(created.id)
        with pytest.raises(NotFoundError):
            await svc.get_instance(created.id)

    @pytest.mark.asyncio
    async def test_docker_registry_test_connection_success(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        instance = await svc.create_instance(
            name="dr-conn-ok",
            url="https://registry.example.com",
            username="user",
            password="valid-pass",
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await svc.test_connection(instance.id)

        assert result["success"] is True
        assert "Docker Registry reachable" in result["message"]

    @pytest.mark.asyncio
    async def test_docker_registry_test_connection_failure(self, db_session: AsyncSession):
        svc = DockerRegistryInstanceService(db_session)
        instance = await svc.create_instance(
            name="dr-conn-fail",
            url="https://registry-down.example.com",
            username="user",
            password="pass",
        )
        import httpx

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            result = await svc.test_connection(instance.id)
        assert result["success"] is False
        assert "Could not reach" in result["message"]


# ═══════════════════════════════════════════════════════════════════════════════
# Helm Repository Instance Service Tests (10 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestHelmRepositoryInstanceService:
    """Unit tests for HelmRepositoryInstanceService CRUD and connection testing."""

    @pytest.mark.asyncio
    async def test_list_helm_repository_instances(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        await svc.create_instance(
            name="helm-prod",
            url="https://charts.prod.example.com",
            username="user",
            password="pass1",
        )
        await svc.create_instance(
            name="helm-staging",
            url="https://charts.staging.example.com",
            username="user",
            password="pass2",
        )
        result = await svc.list_instances()
        assert len(result) == 2
        names = {r.name for r in result}
        assert names == {"helm-prod", "helm-staging"}

    @pytest.mark.asyncio
    async def test_get_helm_repository_instance(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        created = await svc.create_instance(
            name="helm-get", url="https://charts.example.com", username="user", password="secret"
        )
        fetched = await svc.get_instance(created.id)
        assert fetched.name == "helm-get"
        assert fetched.username == "user"

    @pytest.mark.asyncio
    async def test_get_helm_repository_instance_not_found(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        with pytest.raises(NotFoundError):
            await svc.get_instance(99999)

    @pytest.mark.asyncio
    async def test_create_helm_repository_instance(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        instance = await svc.create_instance(
            name="helm-enc",
            url="https://charts.example.com",
            username="user",
            password="super-secret",
        )
        assert instance.password != "super-secret"
        assert decrypt_secret(instance.password) == "super-secret"
        assert instance.status_flag == 4

    @pytest.mark.asyncio
    async def test_create_helm_repository_instance_duplicate_name(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        await svc.create_instance(
            name="helm-dup", url="https://charts1.example.com", username="user", password="pass1"
        )
        with pytest.raises(ConflictError):
            await svc.create_instance(
                name="helm-dup",
                url="https://charts2.example.com",
                username="user",
                password="pass2",
            )

    @pytest.mark.asyncio
    async def test_update_helm_repository_instance(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        created = await svc.create_instance(
            name="helm-old", url="https://old.example.com", username="user", password="pass"
        )
        updated = await svc.update_instance(
            created.id, name="helm-new", url="https://new.example.com"
        )
        assert updated.name == "helm-new"
        assert updated.url == "https://new.example.com"

    @pytest.mark.asyncio
    async def test_update_helm_repository_instance_password(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        created = await svc.create_instance(
            name="helm-rekey",
            url="https://charts.example.com",
            username="user",
            password="old-pass",
        )
        old_ciphertext = created.password
        updated = await svc.update_instance(created.id, password="new-pass")
        assert updated.password != old_ciphertext
        assert decrypt_secret(updated.password) == "new-pass"

    @pytest.mark.asyncio
    async def test_delete_helm_repository_instance(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        created = await svc.create_instance(
            name="helm-del", url="https://charts.example.com", username="user", password="pass"
        )
        await svc.delete_instance(created.id)
        with pytest.raises(NotFoundError):
            await svc.get_instance(created.id)

    @pytest.mark.asyncio
    async def test_helm_repository_test_connection_success(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        instance = await svc.create_instance(
            name="helm-conn-ok",
            url="https://charts.example.com",
            username="user",
            password="valid-pass",
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = await svc.test_connection(instance.id)

        assert result["success"] is True
        assert "Helm Repository reachable" in result["message"]

    @pytest.mark.asyncio
    async def test_helm_repository_test_connection_failure(self, db_session: AsyncSession):
        svc = HelmRepositoryInstanceService(db_session)
        instance = await svc.create_instance(
            name="helm-conn-fail",
            url="https://charts-down.example.com",
            username="user",
            password="pass",
        )
        import httpx

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            result = await svc.test_connection(instance.id)
        assert result["success"] is False
        assert "Could not reach" in result["message"]
