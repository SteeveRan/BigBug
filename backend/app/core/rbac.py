from collections.abc import Callable
from enum import StrEnum

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.database import get_db

security = HTTPBearer()


class RoleName(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.role import UserRole
    from app.models.user import User

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError as e:
        raise UnauthorizedError(str(e)) from e

    user_id: int | None = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Token missing subject")

    result = await db.execute(
        select(User)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
        .where(User.id == int(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    # Attach permissions from JWT payload (if present) for RBAC caching.
    # This avoids an extra DB query in require_permission() for tokens
    # created after Phase 4 (June 2025). Old tokens without permissions
    # will fall back to DB lookup.
    user._cached_permissions = payload.get("permissions", [])

    return user


def require_roles(*roles: RoleName):
    async def dependency(current_user=Depends(get_current_user)):
        user_role_names = {r.name for r in current_user.roles}
        if not any(role.value in user_role_names for role in roles):
            raise ForbiddenError(f"Required roles: {[r.value for r in roles]}")
        return current_user

    return dependency


def require_admin():
    return require_roles(RoleName.ADMIN)


def require_operator():
    return require_roles(RoleName.ADMIN, RoleName.OPERATOR)


def require_viewer():
    return require_roles(RoleName.ADMIN, RoleName.OPERATOR, RoleName.VIEWER)


def require_permission(permission: str) -> Callable:
    """
    FastAPI dependency factory for permission-based access control.

    Usage::

        @router.get("/resource")
        async def handler(
            _: None = Depends(require_permission("resource:read"))
        ):
            ...

    Returns a dependency that:
        1. Gets the current authenticated user
        2. Checks permissions from JWT cache first (if available)
        3. Falls back to DB lookup for old tokens without permissions
        4. Raises HTTP 403 if not authorized
    """

    async def dependency(
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ):
        # Phase 4 optimisation: use cached permissions from JWT payload
        # (set by get_current_user) to avoid a DB round-trip on every
        # permission check. Old tokens that predate this feature have an
        # empty list, which triggers the fallback DB query.
        cached: list[str] = getattr(current_user, "_cached_permissions", [])

        if not cached:
            # Fallback: token was issued before Phase 4 or caching is disabled.
            # Perform the full DB lookup via RBACService.
            from app.services.rbac_service import RBACService

            rbac_service = RBACService(db)
            cached = await rbac_service.get_user_permissions(current_user.id)

        if permission not in cached:
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: '{permission}' required",
            )

        return current_user

    return dependency


def require_scope_permission(
    permission: str,
    resource_type: str,
    resource_id_param: str = "id",
) -> Callable:
    """
    FastAPI dependency factory that checks both a base permission AND
    that the user has scope access to the specific resource.

    Usage::

        @router.get("/api/source-groups/{id}")
        async def get_source_group(
            id: int,
            _: bool = Depends(require_scope_permission("source_groups:read", "source_group")),
        ):
            ...

        @router.post("/api/mirroring/sync-groups/{sync_group_id}/mirrors")
        async def create_mirror(
            sync_group_id: int,
            _: bool = Depends(
                require_scope_permission("sync_groups:write", "sync_group", "sync_group_id")
            ),
        ):
            ...

    :param permission:     Permission string to check (e.g. ``"source_groups:read"``).
    :param resource_type:  Scope resource type — one of ``"source_group"``,
                           ``"credential"`` or ``"sync_group"``.
    :param resource_id_param: Name of the path parameter that holds the resource ID
                              (default ``"id"``).
    :returns: An async dependency that returns ``True`` if both checks pass.

    Behaviour:

    1. Verifies the caller holds *permission* (same logic as
       :func:`require_permission`).
    2. Extracts the resource ID from *request.path_params*.
    3. If the ID is ``None`` (resource not yet created — typical for POST /
       PUT that create a new entity) the scope check is **skipped**.
    4. Otherwise calls :meth:`RBACService.check_scope_access` which grants
       access to admins or users whose effective scope includes the resource.
    5. Raises ``HTTP 403`` when either the permission or the scope check fails.
    """

    async def dependency(
        request: Request,
        current_user=Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> bool:
        # ------------------------------------------------------------------
        # 1. Check base permission (same logic as require_permission)
        # ------------------------------------------------------------------
        cached: list[str] = getattr(current_user, "_cached_permissions", [])

        if not cached:
            from app.services.rbac_service import RBACService

            rbac_service = RBACService(db)
            cached = await rbac_service.get_user_permissions(current_user.id)

        if permission not in cached:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: '{permission}' required",
            )

        # ------------------------------------------------------------------
        # 2. Extract resource ID from path parameters
        # ------------------------------------------------------------------
        resource_id = request.path_params.get(resource_id_param)
        if resource_id is None:
            # Resource not yet created — skip scope check
            return True

        # ------------------------------------------------------------------
        # 3. Scope-based access check
        # ------------------------------------------------------------------
        from app.services.rbac_service import RBACService

        rbac = RBACService(db)
        has_access = await rbac.check_scope_access(current_user.id, resource_type, int(resource_id))

        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: resource not in your role scope",
            )

        return True

    return dependency
