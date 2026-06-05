from enum import StrEnum
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError, ForbiddenError
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
    from app.models.user import User
    from app.models.role import UserRole

    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError as e:
        raise UnauthorizedError(str(e))

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

    return user


def require_roles(*roles: RoleName):
    async def dependency(current_user=Depends(get_current_user)):
        user_role_names = {r.name for r in current_user.roles}
        if not any(role.value in user_role_names for role in roles):
            raise ForbiddenError(
                f"Required roles: {[r.value for r in roles]}"
            )
        return current_user
    return dependency


def require_admin():
    return require_roles(RoleName.ADMIN)


def require_operator():
    return require_roles(RoleName.ADMIN, RoleName.OPERATOR)


def require_viewer():
    return require_roles(RoleName.ADMIN, RoleName.OPERATOR, RoleName.VIEWER)
