"""
@file source_providers/dispatcher.py
@description Factory for selecting and instantiating the correct
             BaseSourceProvider implementation based on provider_type.
             Replaces hard-coded GitHubSourceProvider imports with
             a single dispatch point for all supported source providers.
@dependencies app.models.source_provider.ProviderType,
             app.services.source_provider.BaseSourceProvider,
             .github.GitHubSourceProvider, .gitlab.GitLabSourceProvider
@relatedFiles ./github.py, ./gitlab.py, ../source_provider.py,
              ../../models/source_provider.py
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.source_provider import SourceProvider
    from app.services.source_provider import BaseSourceProvider

logger = logging.getLogger(__name__)


def get_provider_class(provider_type: str) -> type[BaseSourceProvider]:
    """
    Return the concrete :class:`BaseSourceProvider` subclass for the given
    ``provider_type`` string, without instantiating it.

    Args:
        provider_type: One of the values defined in :class:`ProviderType`
                       (``"github"``, ``"gitlab"``, ``"generic"``).

    Returns:
        The provider class (e.g. :class:`GitHubSourceProvider`).

    Raises:
        ValueError: If ``provider_type`` is not a supported value.
    """
    from app.models.source_provider import ProviderType

    # Lazy imports to avoid circular dependencies at module load time.
    if provider_type == ProviderType.github:
        from app.services.source_providers.github import GitHubSourceProvider

        return GitHubSourceProvider

    if provider_type == ProviderType.gitlab:
        from app.services.source_providers.gitlab import GitLabSourceProvider

        return GitLabSourceProvider

    if provider_type == ProviderType.generic:
        from app.services.source_providers.generic_git import GenericGitSourceProvider

        return GenericGitSourceProvider

    raise ValueError(f"Unsupported provider type: {provider_type!r}")


async def create_source_provider(
    provider: SourceProvider,
    credential_secret: str,
) -> BaseSourceProvider:
    """
    Create and return a concrete :class:`BaseSourceProvider` instance for the
    given ORM model.

    The caller is responsible for decrypting the credential secret (e.g. via
    :func:`app.core.secrets.decrypt_secret`) before passing it in.

    Args:
        provider: The :class:`~app.models.source_provider.SourceProvider` ORM
                  model with provider configuration (type, credential ref, etc.).
        credential_secret: The *decrypted* secret string (GitHub/GitLab personal
                            access token).

    Returns:
        An instance of :class:`GitHubSourceProvider`,
        :class:`GitLabSourceProvider`, :class:`GenericGitSourceProvider`,
        or a future provider.

    Raises:
        ValueError: If ``provider.provider_type`` is not a supported member
                    of :class:`~app.models.source_provider.ProviderType`.
    """
    from app.models.source_provider import ProviderType

    # Resolve the class via get_provider_class (validates the type).
    klass = get_provider_class(provider.provider_type)

    logger.info(
        "Creating %s for provider_id=%d label='%s'",
        klass.__name__,
        provider.id,
        provider.label,
    )

    if provider.provider_type == ProviderType.github:
        from app.services.source_providers.github import GitHubSourceProvider

        return GitHubSourceProvider(provider, credential_secret)

    if provider.provider_type == ProviderType.gitlab:
        from app.services.source_providers.gitlab import GitLabSourceProvider

        return GitLabSourceProvider(provider, credential_secret)

    if provider.provider_type == ProviderType.generic:
        from app.services.source_providers.generic_git import GenericGitSourceProvider

        return GenericGitSourceProvider(provider, credential_secret)

    # Defensive — unreachable if get_provider_class validated the type.
    raise ValueError(f"Unsupported provider type: {provider.provider_type}")
