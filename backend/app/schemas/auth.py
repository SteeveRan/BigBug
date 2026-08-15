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


class SSOConfig(BaseModel):
    """Public OIDC parameters the frontend needs to bootstrap keycloak-js."""

    enabled: bool
    url: str
    realm: str
    client_id: str


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
