"""
@file provider_type.py
@description Legacy git source-provider type enum, kept for the V2 git-mirroring
             engine (``services/source_providers/*``). In Providers V3 the
             ``SourceProvider`` model and ``source_providers`` table were removed
             (phase 7F), but the V2 engine and ``source_repository`` schema still
             reference these three values when resolving/parsing git sources.
@dependencies enum
@relatedFiles ../services/source_providers/dispatcher.py,
              ../services/source_repository.py, ../../schemas/source_repository.py
"""

import enum


class ProviderType(enum.StrEnum):
    github = "github"
    gitlab = "gitlab"
    generic = "generic"
