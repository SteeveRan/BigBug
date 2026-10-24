from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class OIDCExchangeRequest(BaseModel):
    """Authorization-code exchange payload sent by the SSO callback page."""

    code: str
    redirect_uri: str
    code_verifier: str
    # Which configured OIDC provider issued the authorization code (ADR-0037).
    provider_id: int
    # OIDC state parameter echoed back by Keycloak on the callback; the
    # frontend puts the provider_id into it, the backend requires the same
    # value here (CSRF-binding the flow to the chosen provider).
    state: str = ""

    @property
    def state_provider_id(self) -> int | None:
        """provider_id extracted from the state parameter, None when absent."""
        part = self.state.split(".", 1)[0] if self.state else ""
        if not part.isdigit():
            return None
        return int(part)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None = None
    is_active: bool
    roles: list[str]

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    roles: list[str] = []


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    is_active: bool | None = None
    roles: list[str] | None = None
