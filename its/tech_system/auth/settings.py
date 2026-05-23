from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    jwt_secret_key: str = Field(
        default="its-dev-auth-secret-change-me-please-rotate",
        alias="AUTH_JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="AUTH_JWT_ALGORITHM")
    jwt_issuer: str = Field(default="its-tech-system", alias="AUTH_JWT_ISSUER")
    access_token_ttl_minutes: int = Field(
        default=30, alias="AUTH_ACCESS_TOKEN_TTL_MINUTES"
    )
    refresh_token_ttl_days: int = Field(default=7, alias="AUTH_REFRESH_TOKEN_TTL_DAYS")
    bootstrap_admin_email: str | None = Field(
        default=None,
        alias="ITS_BOOTSTRAP_ADMIN_EMAIL",
    )

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
