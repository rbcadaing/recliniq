"""Application settings loaded from environment variables.

Every value here must also be documented in ``backend/.env.example``.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class ConfigError(RuntimeError):
    """Raised when configuration is missing or invalid. Never includes secret values."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "RecliniQ"
    app_env: Environment = "local"
    app_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Async SQLAlchemy URL, e.g. postgresql+asyncpg://user:pass@host:5432/db
    database_url: SecretStr
    database_echo: bool = False

    # Comma-separated list of browser origins allowed to call the API.
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    @field_validator("database_url")
    @classmethod
    def _require_asyncpg(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError(
                "must be a PostgreSQL URL using the asyncpg driver (postgresql+asyncpg://...)"
            )
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"


def load_settings(**overrides: object) -> Settings:
    """Build settings, converting validation failures into a secret-free ConfigError."""
    try:
        return Settings(**overrides)  # type: ignore[arg-type]
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in err['loc']).upper()}: {err['msg']}"
            for err in exc.errors(include_input=False, include_url=False)
        )
        raise ConfigError(f"Invalid configuration: {problems}") from None


@lru_cache
def get_settings() -> Settings:
    return load_settings()
