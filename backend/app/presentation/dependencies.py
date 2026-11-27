"""FastAPI dependencies that wire infrastructure into application services."""

from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.accounts.ports import (
    Clock,
    Mailer,
    RateLimiter,
    SpecializationRepository,
    TokenIssuer,
)
from app.application.accounts.services import (
    AccountSettings,
    ConfirmEmail,
    ResendVerification,
    SignUpDoctor,
)
from app.application.accounts.sessions import (
    Login,
    Logout,
    RefreshSession,
    RequestPasswordReset,
    ResetPassword,
    SessionSettings,
)
from app.application.health.service import DatabaseHealthCheck, HealthService
from app.core.config import Settings
from app.infrastructure.accounts.hasher import Argon2PasswordHasher
from app.infrastructure.accounts.jwt import JwtTokenIssuer
from app.infrastructure.accounts.mailer import SmtpMailer
from app.infrastructure.accounts.rate_limiter import PostgresRateLimiter
from app.infrastructure.accounts.repositories import (
    SqlPasswordResetTokenRepository,
    SqlRefreshTokenRepository,
    SqlSpecializationRepository,
    SqlUserRepository,
    SqlVerificationTokenRepository,
)
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.database import Database, SqlDatabaseHealthCheck


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_database(request: Request) -> Database:
    database: Database = request.app.state.database
    return database


async def get_session(
    database: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async for session in database.session():
        yield session


def get_health_service(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> HealthService:
    return HealthService(app_name=settings.app_name, app_version=settings.app_version)


def get_database_health_check(
    database: Annotated[Database, Depends(get_database)],
) -> DatabaseHealthCheck:
    return SqlDatabaseHealthCheck(database.engine)


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
DatabaseHealthCheckDep = Annotated[DatabaseHealthCheck, Depends(get_database_health_check)]


# --- Accounts ---------------------------------------------------------------------------


def get_clock() -> Clock:
    return SystemClock()


def get_mailer(settings: Annotated[Settings, Depends(get_app_settings)]) -> Mailer:
    password = settings.smtp_password.get_secret_value() if settings.smtp_password else None
    return SmtpMailer(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.mail_from,
        username=settings.smtp_username,
        password=password,
        start_tls=settings.smtp_starttls,
    )


def get_rate_limiter(
    database: Annotated[Database, Depends(get_database)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> RateLimiter:
    return PostgresRateLimiter(database.engine, clock)


def get_account_settings(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AccountSettings:
    return AccountSettings(
        app_name=settings.app_name,
        frontend_base_url=settings.frontend_base_url,
        verification_ttl_hours=settings.email_verification_ttl_hours,
        privacy_notice_version=settings.privacy_notice_version,
        rate_limit_window_seconds=settings.rate_limit_window_seconds,
        signup_per_ip=settings.rate_limit_signup_per_ip,
        signup_per_email=settings.rate_limit_signup_per_email,
        resend_per_ip=settings.rate_limit_resend_per_ip,
        resend_per_email=settings.rate_limit_resend_per_email,
    )


def get_specialization_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SpecializationRepository:
    return SqlSpecializationRepository(session)


def _account_ports(
    session: Annotated[AsyncSession, Depends(get_session)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    clock: Annotated[Clock, Depends(get_clock)],
    settings: Annotated[AccountSettings, Depends(get_account_settings)],
) -> dict[str, Any]:
    return {
        "users": SqlUserRepository(session),
        "tokens": SqlVerificationTokenRepository(session),
        "limiter": limiter,
        "clock": clock,
        "settings": settings,
    }


def get_sign_up_doctor(
    ports: Annotated[dict[str, Any], Depends(_account_ports)],
    specializations: Annotated[SpecializationRepository, Depends(get_specialization_repository)],
) -> SignUpDoctor:
    return SignUpDoctor(specializations=specializations, hasher=Argon2PasswordHasher(), **ports)


def get_confirm_email(ports: Annotated[dict[str, Any], Depends(_account_ports)]) -> ConfirmEmail:
    return ConfirmEmail(**ports)


def get_resend_verification(
    ports: Annotated[dict[str, Any], Depends(_account_ports)],
) -> ResendVerification:
    return ResendVerification(**ports)


MailerDep = Annotated[Mailer, Depends(get_mailer)]
SpecializationRepositoryDep = Annotated[
    SpecializationRepository, Depends(get_specialization_repository)
]
SignUpDoctorDep = Annotated[SignUpDoctor, Depends(get_sign_up_doctor)]
ConfirmEmailDep = Annotated[ConfirmEmail, Depends(get_confirm_email)]
ResendVerificationDep = Annotated[ResendVerification, Depends(get_resend_verification)]


# --- Sessions (US-01.3) -----------------------------------------------------------------


def get_token_issuer(
    settings: Annotated[Settings, Depends(get_app_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> TokenIssuer:
    return JwtTokenIssuer(
        secret=settings.jwt_secret.get_secret_value(),
        ttl_minutes=settings.access_token_ttl_minutes,
        clock=clock,
    )


def get_session_settings(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> SessionSettings:
    return SessionSettings(
        app_name=settings.app_name,
        frontend_base_url=settings.frontend_base_url,
        refresh_token_ttl_days=settings.refresh_token_ttl_days,
        password_reset_ttl_minutes=settings.password_reset_ttl_minutes,
        login_window_seconds=settings.rate_limit_login_window_seconds,
        login_per_ip=settings.rate_limit_login_per_ip,
        login_per_email=settings.rate_limit_login_per_email,
        forgot_window_seconds=settings.rate_limit_window_seconds,
        forgot_per_ip=settings.rate_limit_forgot_per_ip,
        forgot_per_email=settings.rate_limit_forgot_per_email,
    )


SessionSettingsDep = Annotated[SessionSettings, Depends(get_session_settings)]
TokenIssuerDep = Annotated[TokenIssuer, Depends(get_token_issuer)]
ClockDep = Annotated[Clock, Depends(get_clock)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


def get_login(
    session: SessionDep,
    issuer: TokenIssuerDep,
    limiter: RateLimiterDep,
    clock: ClockDep,
    settings: SessionSettingsDep,
) -> Login:
    return Login(
        hasher=Argon2PasswordHasher(),
        limiter=limiter,
        users=SqlUserRepository(session),
        refresh_tokens=SqlRefreshTokenRepository(session),
        issuer=issuer,
        clock=clock,
        settings=settings,
    )


def get_refresh_session(
    session: SessionDep, issuer: TokenIssuerDep, clock: ClockDep, settings: SessionSettingsDep
) -> RefreshSession:
    return RefreshSession(
        users=SqlUserRepository(session),
        refresh_tokens=SqlRefreshTokenRepository(session),
        issuer=issuer,
        clock=clock,
        settings=settings,
    )


def get_logout(session: SessionDep, clock: ClockDep) -> Logout:
    return Logout(refresh_tokens=SqlRefreshTokenRepository(session), clock=clock)


def get_request_password_reset(
    session: SessionDep, limiter: RateLimiterDep, clock: ClockDep, settings: SessionSettingsDep
) -> RequestPasswordReset:
    return RequestPasswordReset(
        users=SqlUserRepository(session),
        reset_tokens=SqlPasswordResetTokenRepository(session),
        limiter=limiter,
        clock=clock,
        settings=settings,
    )


def get_reset_password(session: SessionDep, clock: ClockDep) -> ResetPassword:
    return ResetPassword(
        users=SqlUserRepository(session),
        reset_tokens=SqlPasswordResetTokenRepository(session),
        refresh_tokens=SqlRefreshTokenRepository(session),
        hasher=Argon2PasswordHasher(),
        clock=clock,
    )


LoginDep = Annotated[Login, Depends(get_login)]
RefreshSessionDep = Annotated[RefreshSession, Depends(get_refresh_session)]
LogoutDep = Annotated[Logout, Depends(get_logout)]
RequestPasswordResetDep = Annotated[RequestPasswordReset, Depends(get_request_password_reset)]
ResetPasswordDep = Annotated[ResetPassword, Depends(get_reset_password)]
