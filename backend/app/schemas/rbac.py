"""
Pydantic schemas for RBAC endpoints.

Used by the RBAC API layer to validate request/response payloads
and serialize Permission / Role models.
"""

from pydantic import BaseModel, ConfigDict


class PermissionOut(BaseModel):
    """Single permission as returned by the API."""

    id: int
    name: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class RoleOut(BaseModel):
    """Basic role info without embedded permissions."""

    id: int
    name: str
    description: str | None
    is_custom: bool
    created_by_user_id: int | None
    source_group_ids: list[int] | None = None
    credential_ids: list[int] | None = None
    sync_group_ids: list[int] | None = None
    provider_ids: list[int] | None = None

    model_config = ConfigDict(from_attributes=True)


class RoleDetailOut(BaseModel):
    """Role with its full list of assigned permissions and user count."""

    id: int
    name: str
    description: str | None
    is_custom: bool
    created_by_user_id: int | None
    users_count: int = 0
    permissions: list[PermissionOut]

    model_config = ConfigDict(from_attributes=True)


class RoleCreate(BaseModel):
    """Payload for creating a new custom role."""

    name: str
    description: str | None = None
    permission_names: list[str]  # ["mirrors:read", "helm:write"]


class RoleUpdate(BaseModel):
    """Payload for updating an existing role. All fields optional — only
    supplied values are applied."""

    name: str | None = None
    description: str | None = None
    permission_names: list[str] | None = None  # None → don't change permissions


class UserPermissionsOut(BaseModel):
    """Response for ``GET /auth/me/permissions``."""

    user_id: int
    role: str
    permissions: list[str]


class RoleScopeOut(BaseModel):
    """Scope assigned to a role."""

    source_group_ids: list[int] = []
    credential_ids: list[int] = []
    sync_group_ids: list[int] = []
    provider_ids: list[int] = []

    model_config = ConfigDict(from_attributes=True)


class RoleScopeUpdate(BaseModel):
    """Request to update role scope."""

    source_group_ids: list[int] | None = None
    credential_ids: list[int] | None = None
    sync_group_ids: list[int] | None = None
    provider_ids: list[int] | None = None
