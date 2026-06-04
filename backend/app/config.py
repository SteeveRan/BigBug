from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Literal


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

    # Keycloak OIDC
    keycloak_url: str = "http://localhost:8180"
    keycloak_realm: str = "bigbug"
    keycloak_client_id: str = "bigbug-backend"
    keycloak_client_secret: str = ""

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

    @property
    def keycloak_openid_config_url(self) -> str:
        return (
            f"{self.keycloak_url}/realms/{self.keycloak_realm}"
            "/.well-known/openid-configuration"
        )

    @property
    def keycloak_token_url(self) -> str:
        return (
            f"{self.keycloak_url}/realms/{self.keycloak_realm}"
            "/protocol/openid-connect/token"
        )

    @property
    def keycloak_jwks_url(self) -> str:
        return (
            f"{self.keycloak_url}/realms/{self.keycloak_realm}"
            "/protocol/openid-connect/certs"
        )


settings = Settings()
