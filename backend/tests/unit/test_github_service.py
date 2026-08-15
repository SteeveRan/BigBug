"""
@file test_github_service.py
@description Unit tests for GitHubService provider resolution (phase 7B):
             resolves GitHub provider from resource_providers (private with
             credential, then anonymous public fallback) and builds the PyGithub
             client from ResourceProvider.
@dependencies pytest-asyncio, backend/tests/conftest.py
@relatedFiles ../../app/services/github.py, ../../app/models/resource_provider.py,
               ../../app/models/credential.py
"""

from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secrets import encrypt_secret
from app.models.credential import Credential, CredentialType
from app.models.resource_provider import (
    ProviderCategory,
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)
from app.services.github import GitHubService


async def _public_provider(db: AsyncSession, name: str = "github-anonymous") -> ResourceProvider:
    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.github,
        category=ProviderCategory.public,
        direction=ProviderDirection.external,
        name=name,
        label=name,
        is_default=True,
    )
    db.add(provider)
    await db.flush()
    return provider


async def _private_provider(
    db: AsyncSession,
    name: str = "github-private",
    token: str | None = "ghp_test_token",
) -> ResourceProvider:
    credential = Credential(
        name=f"{name}-cred",
        credential_type=CredentialType.github_token,
        provider="github",
        encrypted_secret=encrypt_secret(token) if token else None,
    )
    db.add(credential)
    await db.flush()

    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.github,
        category=ProviderCategory.private,
        direction=ProviderDirection.external,
        name=name,
        label=name,
        credential_id=credential.id,
        owner_user_id=1,
    )
    db.add(provider)
    await db.flush()
    return provider


def _in_memory_provider(
    *,
    category: ProviderCategory = ProviderCategory.public,
    config: dict | None = None,
    secret: str | None = None,
) -> ResourceProvider:
    """Build a ResourceProvider with an in-memory credential relationship.

    Assigning ``provider.credential`` directly avoids an async lazy load when
    the sync ``_get_client`` method accesses the relationship.
    """
    provider = ResourceProvider(
        domain=ProviderDomain.git,
        subtype=ProviderSubtype.github,
        category=category,
        direction=ProviderDirection.external,
        name="gh",
        label="GitHub",
        config=config or {},
    )
    if secret is not None:
        provider.credential = Credential(
            name="gh-cred",
            credential_type=CredentialType.github_token,
            provider="github",
            encrypted_secret=encrypt_secret(secret),
        )
    return provider


class TestGetDefaultProvider:
    async def test_prefers_private_provider_with_credential(self, db_session: AsyncSession):
        public = await _public_provider(db_session)
        private = await _private_provider(db_session)

        resolved = await GitHubService.get_default_provider(db_session)

        assert resolved is not None
        assert resolved.id == private.id
        assert resolved.credential_id == private.credential_id
        assert public.id != resolved.id

    async def test_falls_back_to_anonymous_public(self, db_session: AsyncSession):
        public = await _public_provider(db_session)

        resolved = await GitHubService.get_default_provider(db_session)

        assert resolved is not None
        assert resolved.id == public.id
        assert resolved.credential_id is None

    async def test_returns_none_without_providers(self, db_session: AsyncSession):
        assert await GitHubService.get_default_provider(db_session) is None


class TestGetClient:
    def test_anonymous_public_client_has_no_token(self):
        provider = _in_memory_provider()

        with patch("app.services.github.Github") as mock_gh:
            GitHubService()._get_client(provider)

        mock_gh.assert_called_once_with()

    def test_private_provider_uses_decrypted_token(self):
        provider = _in_memory_provider(
            category=ProviderCategory.private,
            secret="ghp_secret_token",
        )

        with patch("app.services.github.Github") as mock_gh:
            GitHubService()._get_client(provider)

        mock_gh.assert_called_once_with("ghp_secret_token")

    def test_config_api_url_is_passed_as_base_url(self):
        provider = _in_memory_provider(
            config={"api_url": "https://github.example.com/api/v3"},
        )

        with patch("app.services.github.Github") as mock_gh:
            GitHubService()._get_client(provider)

        mock_gh.assert_called_once_with(base_url="https://github.example.com/api/v3")
