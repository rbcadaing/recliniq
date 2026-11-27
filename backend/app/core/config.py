"""Application settings loaded from environment variables.

Every value here must also be documented in ``backend/.env.example``.
"""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, SecretStr, ValidationError, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]

# Only acceptable in local/test. Anywhere else, startup fails unless JWT_SECRET is set properly.
DEV_JWT_SECRET = "local-dev-only-jwt-secret-change-me-0000"  # noqa: S105
MIN_JWT_SECRET_BYTES = 32


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

    # Base URL of the frontend, used to build links in emails (no trailing slash needed).
    frontend_base_url: str = "http://localhost:5173"

    # Outbound email (SMTP). Locally this points at Mailpit.
    mail_from: str = "RecliniQ <no-reply@recliniq.local>"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False

    # Accounts
    email_verification_ttl_hours: int = Field(default=24, ge=1)
    privacy_notice_version: str = "2026-11-draft"

    # Rate limits: max attempts per window, per client IP and per submitted email.
    rate_limit_window_seconds: int = Field(default=3600, ge=1)
    rate_limit_signup_per_ip: int = Field(default=5, ge=1)
    rate_limit_signup_per_email: int = Field(default=3, ge=1)
    rate_limit_resend_per_ip: int = Field(default=10, ge=1)
    rate_limit_resend_per_email: int = Field(default=3, ge=1)
    rate_limit_login_window_seconds: int = Field(default=900, ge=1)
    rate_limit_login_per_ip: int = Field(default=30, ge=1)
    rate_limit_login_per_email: int = Field(default=10, ge=1)
    rate_limit_forgot_per_ip: int = Field(default=10, ge=1)
    rate_limit_forgot_per_email: int = Field(default=3, ge=1)

    # Sessions. JWT_SECRET signs access tokens (HS256); required outside local/test.
    jwt_secret: SecretStr = Field(default=SecretStr(DEV_JWT_SECRET), validate_default=True)
    access_token_ttl_minutes: int = Field(default=15, ge=1)
    refresh_token_ttl_days: int = Field(default=30, ge=1)
    password_reset_ttl_minutes: int = Field(default=60, ge=1)

    @field_validator("database_url")
    @classmethod
    def _require_asyncpg(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError(
                "must be a PostgreSQL URL using the asyncpg driver (postgresql+asyncpg://...)"
            )
        return value

    @field_validator("jwt_secret")
    @classmethod
    def _strong_secret_outside_dev(cls, value: SecretStr, info: ValidationInfo) -> SecretStr:
        if info.data.get("app_env") in ("local", "test"):
            return value
        secret = value.get_secret_value()
        if secret == DEV_JWT_SECRET or len(secret.encode()) < MIN_JWT_SECRET_BYTES:
            raise ValueError(
                f"must be set to a random secret of at least {MIN_JWT_SECRET_BYTES} bytes "
                "outside local/test"
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
