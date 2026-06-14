"""
@file source_providers/__init__.py
@description Package for concrete source provider implementations
             (GitHub, GitLab, Generic) plus the provider
             dispatcher factory.
@dependencies .github.GitHubSourceProvider, .gitlab.GitLabSourceProvider,
             .dispatcher.create_source_provider, .dispatcher.get_provider_class
@relatedFiles ./github.py, ./gitlab.py, ./dispatcher.py, ../source_provider.py
"""

from app.services.source_provider import BaseSourceProvider
from app.services.source_providers.dispatcher import (
    create_source_provider,
    get_provider_class,
)
from app.services.source_providers.github import GitHubSourceProvider
from app.services.source_providers.gitlab import GitLabSourceProvider

__all__ = [
    "BaseSourceProvider",
    "GitHubSourceProvider",
    "GitLabSourceProvider",
    "create_source_provider",
    "get_provider_class",
]
