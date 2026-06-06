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

    model_config = ConfigDict(from_attributes=True)


class RoleDetailOut(BaseModel):
    """Role with its full list of assigned permissions."""

    id: int
    name: str
    description: str | None
    is_custom: bool
    created_by_user_id: int | None
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
