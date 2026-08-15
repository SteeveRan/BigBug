"""
@file source_providers/dispatcher.py
@description Factory for selecting and instantiating the correct
             BaseSourceProvider implementation based on provider_type.
             Since Providers V3 phase 7E the input is exclusively a
             ``ResourceProvider`` (domain=git, direction=external); the
             legacy ``SourceProvider`` path has been removed.
@dependencies app.models.resource_provider,
              app.services.source_provider.BaseSourceProvider,
              .github.GitHubSourceProvider, .gitlab.GitLabSourceProvider
@relatedFiles ./github.py, ./gitlab.py, ../source_provider.py,
              ../../models/resource_provider.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.exceptions import BadRequestError
from app.models.resource_provider import (
    ProviderDirection,
    ProviderDomain,
    ProviderSubtype,
    ResourceProvider,
)

if TYPE_CHECKING:
    from app.services.source_provider import BaseSourceProvider

logger = logging.getLogger(__name__)

# ResourceProvider.subtype → legacy ProviderType value expected by the V2 classes
_SUBTYPE_TO_PROVIDER_TYPE = {
    ProviderSubtype.github: "github",
    ProviderSubtype.gitlab: "gitlab",
    ProviderSubtype.generic_git: "generic",
}


@dataclass
class _V2ProviderAdapter:
    """Adapt a ``ResourceProvider`` to the SourceProvider shape the V2
    provider classes read (``id``, ``label``, ``credential``).

    Kept as a plain dataclass (not an ORM object) — the V2 classes only
    access attributes, never the session. Removed in phase 7 together with
    the V2 classes.
    """

    id: int
    label: str
    provider_type: str
    is_anon: bool
    credential: Any = None
    base_url: str | None = field(default=None)


def adapt_resource_provider(provider: ResourceProvider) -> _V2ProviderAdapter:
    """Map a git ``ResourceProvider`` onto the legacy V2 provider shape.

    Raises:
        BadRequestError: when the provider is not a git/external source
                         (mirroring sources are external by definition, 11.3.4).
    """
    if provider.domain != ProviderDomain.git:
        raise BadRequestError(
            f"Provider {provider.id} is domain '{provider.domain}', expected 'git'"
        )
    if provider.direction != ProviderDirection.external:
        raise BadRequestError(
            f"Provider {provider.id} is direction '{provider.direction}', "
            "expected 'external' (mirroring sources are external)"
        )

    provider_type = _SUBTYPE_TO_PROVIDER_TYPE.get(provider.subtype)
    if provider_type is None:
        raise BadRequestError(
            f"Provider {provider.id} subtype '{provider.subtype}' is not a git source"
        )

    return _V2ProviderAdapter(
        id=provider.id,
        label=provider.label,
        provider_type=provider_type,
        # public providers are anonymous by definition (Providers V3, section 2)
        is_anon=provider.credential_id is None,
        credential=provider.credential,
        base_url=provider.base_url,
    )


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
    from app.models.provider_type import ProviderType

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
    provider: ResourceProvider,
    credential_secret: str | None,
) -> BaseSourceProvider:
    """
    Create and return a concrete :class:`BaseSourceProvider` instance.

    Since Providers V3 phase 7E the input is exclusively a
    :class:`~app.models.resource_provider.ResourceProvider`
    (domain=git, direction=external) — it is adapted onto the legacy V2
    shape.

    The caller is responsible for decrypting the credential secret (e.g. via
    :func:`app.core.secrets.decrypt_secret`) before passing it in.
    Pass ``None`` for anonymous providers (public, no credential).

    Args:
        provider: The git ``ResourceProvider`` ORM model.
        credential_secret: The *decrypted* secret string (GitHub/GitLab personal
                            access token), or ``None`` for anonymous providers.

    Returns:
        An instance of :class:`GitHubSourceProvider`,
        :class:`GitLabSourceProvider`, :class:`GenericGitSourceProvider`,
        or a future provider.

    Raises:
        BadRequestError: If a ResourceProvider is not git/external or has an
                         unsupported subtype.
        ValueError: If a non-anonymous provider has no ``credential_secret``.
    """
    provider = adapt_resource_provider(provider)

    # Resolve the class via get_provider_class (validates the type).
    klass = get_provider_class(provider.provider_type)

    # For anonymous providers, ignore any passed credential
    if provider.is_anon:
        credential_secret = None

    # Non-anonymous providers MUST have a credential
    if not provider.is_anon and credential_secret is None:
        raise ValueError(
            f"Provider id={provider.id} is not anonymous but no credential_secret provided"
        )

    logger.info(
        "Creating %s for provider_id=%d label='%s' anon=%s",
        klass.__name__,
        provider.id,
        provider.label,
        provider.is_anon,
    )

    if provider.provider_type == "github":
        from app.services.source_providers.github import GitHubSourceProvider

        return GitHubSourceProvider(provider, credential_secret)

    if provider.provider_type == "gitlab":
        from app.services.source_providers.gitlab import GitLabSourceProvider

        return GitLabSourceProvider(provider, credential_secret)

    if provider.provider_type == "generic":
        from app.services.source_providers.generic_git import GenericGitSourceProvider

        return GenericGitSourceProvider(provider, credential_secret)

    # Defensive — unreachable if get_provider_class validated the type.
    raise ValueError(f"Unsupported provider type: {provider.provider_type}")
