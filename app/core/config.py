from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "task-manager-api"
    api_v1_prefix: str = "/v1"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False

    # Individual DB credentials rather than a single DSN so the password is typed
    # as SecretStr end-to-end (never a plain str the logger/repr can leak).
    postgres_user: str = "app"
    postgres_password: SecretStr
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "task_manager"
    database_echo: bool = False

    # No wildcard default: every allowed browser origin must be listed explicitly.
    cors_origins: list[str] = Field(default_factory=list)

    # High-entropy signing key, no shipped default — must come from the environment
    # (e.g. `openssl rand -hex 32`) or a secrets manager, never checked into source.
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15

    rate_limit_default: str = "100/minute"
    rate_limit_auth: str = "10/minute"

    log_level: str = "INFO"

    @field_validator("jwt_secret_key")
    @classmethod
    def _reject_weak_jwt_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("jwt_secret_key must be at least 32 characters (256 bits) long")
        return value

    @field_validator("cors_origins")
    @classmethod
    def _reject_wildcard_origin(cls, value: list[str]) -> list[str]:
        if "*" in value:
            raise ValueError("cors_origins must list explicit origins; wildcard '*' is not allowed")
        return value

    @property
    def database_url(self) -> PostgresDsn:
        return PostgresDsn(
            f"postgresql+asyncpg://{self.postgres_user}:"
            f"{self.postgres_password.get_secret_value()}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    # Required fields (postgres_password, jwt_secret_key) are populated by
    # pydantic-settings from the environment/.env, not by this call site.
    return Settings()  # type: ignore[call-arg]
