from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "BigBug DevOps Service"
    environment: Literal["development", "production", "test"] = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://bigbug:bigbug@localhost:5432/bigbug"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg:// scheme for async support")
        return v

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    secret_key: str = "changeme-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Symmetric encryption (Fernet) for credentials at rest (Helm/Docker
    # registry passwords). Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Empty string means encrypted columns cannot be written/read — features
    # depending on it (Helm chart / Docker image sync) fail loudly at use.
    encryption_key: str = ""

    # Keycloak OIDC
    keycloak_url: str = "http://localhost:8180"
    keycloak_realm: str = "bigbug"
    keycloak_client_id: str = "bigbug-backend"
    keycloak_client_secret: str = ""
    # WHY: the browser performs the Authorization Code + PKCE flow against a
    # separate *public* client; the backend only needs its id to expose it to
    # the SPA via /auth/sso/config.
    keycloak_frontend_client_id: str = "bigbug-frontend"
    # WHY: Backend uses keycloak_url for server-to-server OIDC (token exchange,
    # JWKS fetching), but the browser needs a publicly accessible URL.
    # In Docker: backend uses http://keycloak:8180, browser uses http://localhost:8180
    keycloak_public_url: str = "http://localhost:8180"
    # WHY: short, dedicated timeout for OIDC HTTP calls keeps slow IDP
    # responses from blocking request workers indefinitely.
    keycloak_http_timeout_seconds: float = 10.0
    # WHY: caching the JWKS avoids hitting Keycloak on every token validation
    # while still allowing key rotation within the configured window.
    keycloak_jwks_cache_ttl_seconds: int = 600

    # GitLab
    gitlab_url: str = "http://gitlab.local:8080"
    gitlab_token: str = ""

    # GitHub
    github_token: str = ""

    # Schedules (cron expressions)
    default_sync_cron: str = "0 2 * * *"
    default_build_cron: str = "0 3 * * 0"

    # Stale threshold
    default_stale_threshold_days: int = 30

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_login: str = "5/minute"
    rate_limit_oidc_exchange: str = "3/minute"
    rate_limit_global: str = "100/minute"

    @property
    def keycloak_openid_config_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/.well-known/openid-configuration"

    @property
    def keycloak_token_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/token"

    @property
    def keycloak_jwks_url(self) -> str:
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"


settings = Settings()
