from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class BadRequestError(HTTPException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ExternalServiceError(HTTPException):
    def __init__(self, service: str, detail: str = ""):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"External service error ({service}): {detail}",
        )


# --- OIDC / SSO ---------------------------------------------------------------
# These are plain exceptions (not HTTPException) on purpose: the OIDC service is
# a pure domain layer that must stay framework-agnostic and unit-testable. The
# API layer (app/api/auth.py) catches them and maps to the appropriate HTTP
# response, keeping transport concerns out of the service.


class OIDCError(RuntimeError):
    """Base class for all OIDC/SSO failures raised by the OIDC service."""


class OIDCExchangeError(OIDCError):
    """The authorization-code exchange with Keycloak failed (network / 4xx)."""


class OIDCInvalidTokenError(OIDCError):
    """The ID token failed signature, issuer, audience or expiry validation."""


class OIDCProvisioningError(OIDCError):
    """A valid token was received but the local user could not be provisioned."""


# --- RBAC ---------------------------------------------------------------
# These are plain exceptions (not HTTPException) on purpose: the RBAC
# service is a pure domain layer that must stay framework-agnostic and
# unit-testable. The API layer catches them and maps to the appropriate
# HTTP response, keeping transport concerns out of the service.


class PermissionNotFoundError(RuntimeError):
    """One or more requested permission names do not exist in the system."""


class CannotModifyBuiltinRoleError(RuntimeError):
    """Attempted to modify or delete a built-in (non-custom) role."""


class RoleHasUsersError(RuntimeError):
    """Cannot delete a role that still has users assigned to it."""


class RoleNotFoundError(RuntimeError):
    """The requested role does not exist."""

