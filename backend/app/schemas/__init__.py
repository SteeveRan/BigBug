"""
@file __init__.py
@description Schema package initialization.
             Imports all cross-referenced types and calls model_rebuild()
             on every Pydantic model that uses forward references to resolve
             circular dependencies cleanly — no TYPE_CHECKING hacks needed
             at the API layer.
@dependencies pydantic
@relatedFiles ./mirror.py, ./mirror_log.py, ./source_repository.py,
              ./source_group.py, ./source_provider.py, ./sync_group.py,
              ./credential.py, ./pipeline.py
"""

# ──── Import all cross-referenced types for model_rebuild() ──────────────
# Import order: leaf modules first (no schema→schema deps), then those
# that only reference already-imported modules.  TYPE_CHECKING guards in
# each file prevent import-time circular failures.
# credential.py — no schema imports, safe to import first
from app.schemas.credential import CredentialOut

# mirror.py — references mirror_log + source_repository + sync_group
from app.schemas.mirror import MirrorDetailOut, MirrorListOut

# mirror_log.py — references mirror + pipeline
from app.schemas.mirror_log import MirrorLogOut

# pipeline.py — only imports from integrations (non-circular)
from app.schemas.pipeline import PipelineOut, PipelineRunOut
from app.schemas.rbac import (
    PermissionOut,
    RoleCreate,
    RoleDetailOut,
    RoleOut,
    RoleUpdate,
    UserPermissionsOut,
)

# source_group.py — references source_provider + source_repository
from app.schemas.source_group import SourceGroupDetailOut, SourceGroupListOut

# source_provider.py — only references credential (already imported)
from app.schemas.source_provider import SourceProviderOut

# source_repository.py — references source_group + mirror
from app.schemas.source_repository import SourceRepositoryDetailOut, SourceRepositoryListOut

# sync_group.py — references pipeline
from app.schemas.sync_group import SyncGroupOut

# ──── Rebuild models with forward references ───────────────────────────
# Every type that appears inside Optional["..."] or list["..."] in any
# of the rebuilt models must be present in this namespace.

_namespace: dict[str, object] = {
    "CredentialOut": CredentialOut,
    "SourceProviderOut": SourceProviderOut,
    "SourceGroupListOut": SourceGroupListOut,
    "SourceGroupDetailOut": SourceGroupDetailOut,
    "SourceRepositoryListOut": SourceRepositoryListOut,
    "SourceRepositoryDetailOut": SourceRepositoryDetailOut,
    "MirrorListOut": MirrorListOut,
    "MirrorDetailOut": MirrorDetailOut,
    "MirrorLogOut": MirrorLogOut,
    "SyncGroupOut": SyncGroupOut,
    "PipelineOut": PipelineOut,
    "PipelineRunOut": PipelineRunOut,
}

for _model_cls in (
    MirrorListOut,
    MirrorDetailOut,
    MirrorLogOut,
    SourceRepositoryDetailOut,
    SourceGroupDetailOut,
    SourceProviderOut,
    SyncGroupOut,
):
    _model_cls.model_rebuild(_types_namespace=_namespace)
