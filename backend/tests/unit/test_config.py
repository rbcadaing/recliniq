import pytest

from app.core.config import ConfigError, load_settings

SECRET = "sup3r-s3cret-pw"


def test_missing_database_url_names_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ConfigError) as exc_info:
        load_settings(_env_file=None)
    assert "DATABASE_URL" in str(exc_info.value)


def test_invalid_database_url_does_not_echo_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"mysql://user:{SECRET}@db/app")
    with pytest.raises(ConfigError) as exc_info:
        load_settings(_env_file=None)
    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert SECRET not in message
    assert exc_info.value.__cause__ is None


def test_cors_origins_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/app")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test,")
    settings = load_settings(_env_file=None)
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_database_url_is_masked_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", f"postgresql+asyncpg://u:{SECRET}@db/app")
    settings = load_settings(_env_file=None)
    assert SECRET not in repr(settings)


def test_account_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/app")
    settings = load_settings(_env_file=None)
    assert settings.frontend_base_url == "http://localhost:5173"
    assert settings.smtp_port == 1025
    assert settings.smtp_password is None
    assert settings.email_verification_ttl_hours == 24
    assert settings.rate_limit_window_seconds == 3600
    assert settings.rate_limit_signup_per_ip == 5
    assert settings.rate_limit_signup_per_email == 3
    assert settings.rate_limit_resend_per_ip == 10
    assert settings.rate_limit_resend_per_email == 3


def test_account_settings_overrides_and_secret_masking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/app")
    monkeypatch.setenv("SMTP_HOST", "mailpit")
    monkeypatch.setenv("SMTP_PASSWORD", SECRET)
    monkeypatch.setenv("RATE_LIMIT_SIGNUP_PER_IP", "50")
    settings = load_settings(_env_file=None)
    assert settings.smtp_host == "mailpit"
    assert settings.rate_limit_signup_per_ip == 50
    assert SECRET not in repr(settings)


def test_invalid_rate_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/app")
    monkeypatch.setenv("RATE_LIMIT_SIGNUP_PER_IP", "0")
    with pytest.raises(ConfigError, match="RATE_LIMIT_SIGNUP_PER_IP"):
        load_settings(_env_file=None)


def test_session_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/app")
    settings = load_settings(_env_file=None)
    assert settings.access_token_ttl_minutes == 15
    assert settings.refresh_token_ttl_days == 30
    assert settings.password_reset_ttl_minutes == 60
    assert settings.rate_limit_login_window_seconds == 900
    assert len(settings.jwt_secret.get_secret_value()) >= 32  # dev default in local


@pytest.mark.parametrize(
    "secret",
    [None, "too-short-secret", "local-dev-only-jwt-secret-change-me-0000"],
    ids=["missing", "short", "dev-default"],
)
def test_production_requires_strong_jwt_secret(
    monkeypatch: pytest.MonkeyPatch, secret: str | None
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/app")
    monkeypatch.setenv("APP_ENV", "production")
    if secret is None:
        monkeypatch.delenv("JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("JWT_SECRET", secret)

    with pytest.raises(ConfigError) as exc_info:
        load_settings(_env_file=None)

    message = str(exc_info.value)
    assert "JWT_SECRET" in message
    if secret:
        assert secret not in message


def test_production_accepts_strong_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db/app")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 48)
    assert load_settings(_env_file=None).jwt_secret.get_secret_value() == "x" * 48
