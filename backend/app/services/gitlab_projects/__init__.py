"""GitlabProject management service package.

Exposes :class:`GitlabProjectService` plus component presets and file/tag
helpers. The provider client factory lives in ``_clients.py`` and is re-exported
by ``pipeline/_clients.py`` for backward compatibility.
"""

from app.services.gitlab_projects._clients import (
    _get_gitlab_provider_or_404,
    get_provider_gitlab_client,
)
from app.services.gitlab_projects._service import GitlabProjectService

__all__ = [
    "GitlabProjectService",
    "get_provider_gitlab_client",
    "_get_gitlab_provider_or_404",
]
