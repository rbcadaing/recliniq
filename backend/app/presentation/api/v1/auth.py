"""Public account endpoints: sign-up, email verification, sessions, and password reset."""

import uuid
from typing import Annotated, Any, Self

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.application.accounts.ports import EmailMessage, Mailer
from app.application.accounts.services import DoctorSignUp
from app.application.accounts.sessions import IssuedSession, RefreshRejected
from app.domain.accounts.passwords import MAX_PASSWORD_LENGTH, check_password_policy
from app.domain.accounts.values import parse_email, parse_ph_mobile, parse_prc_license
from app.domain.errors import InvalidRefreshTokenError
from app.presentation.dependencies import (
    ConfirmEmailDep,
    LoginDep,
    LogoutDep,
    MailerDep,
    RefreshSessionDep,
    RequestPasswordResetDep,
    ResendVerificationDep,
    ResetPasswordDep,
    SignUpDoctorDep,
)
from app.presentation.errors import error_response
from app.presentation.schemas import ErrorEnvelope

router = APIRouter(prefix="/auth", tags=["auth"])

SIGNUP_MESSAGE = "Check your email for a link to verify your account."
RESEND_MESSAGE = "If this email needs verifying, we've sent a new link."
VERIFIED_MESSAGE = "Your email is verified."

Name = Annotated[str, Field(min_length=1, max_length=100)]


class MessageResponse(BaseModel):
    message: str


class DoctorSignUpRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    first_name: Name
    middle_name: Annotated[str, Field(max_length=100)] | None = None
    last_name: Name
    email: str = Field(examples=["juan.delacruz@example.com"])
    mobile: str = Field(examples=["0917 123 4567"], description="Philippine mobile number")
    password: str = Field(
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH * 4,  # policy checks the normalized length
        repr=False,
        json_schema_extra={"format": "password"},
    )
    specialization_id: uuid.UUID
    prc_license_no: str = Field(examples=["0012345"], description="1 to 7 digits")
    privacy_consent: bool = Field(description="Must be true: the privacy notice was accepted")

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return parse_email(value)

    @field_validator("mobile")
    @classmethod
    def _mobile(cls, value: str) -> str:
        return parse_ph_mobile(value)

    @field_validator("prc_license_no")
    @classmethod
    def _prc(cls, value: str) -> str:
        return parse_prc_license(value)

    @field_validator("middle_name")
    @classmethod
    def _blank_middle_name(cls, value: str | None) -> str | None:
        return value or None

    @field_validator("password")
    @classmethod
    def _password(cls, value: str, info: ValidationInfo) -> str:
        check_password_policy(value, email=info.data.get("email"))
        return value

    @field_validator("privacy_consent")
    @classmethod
    def _consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("you must accept the privacy notice")
        return value

    def to_command(self: Self) -> DoctorSignUp:
        return DoctorSignUp(
            first_name=self.first_name,
            middle_name=self.middle_name,
            last_name=self.last_name,
            email=self.email,
            mobile=self.mobile,
            password=self.password,
            specialization_id=self.specialization_id,
            prc_license_no=self.prc_license_no,
        )


class ResendRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return parse_email(value)


class ConfirmRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


def _client_ip(request: Request) -> str:
    # Behind a reverse proxy this needs trusted X-Forwarded-For handling (see design D2).
    return request.client.host if request.client else "unknown"


def _send_later(background: BackgroundTasks, mailer: Mailer, emails: list[EmailMessage]) -> None:
    # Sent after the response: delivery can't fail or slow down the request.
    for email in emails:
        background.add_task(mailer.send, email)


_RATE_LIMITED: dict[int | str, dict[str, Any]] = {
    429: {"model": ErrorEnvelope, "description": "Too many attempts (Retry-After)"}
}


@router.post(
    "/doctors/signup",
    status_code=202,
    response_model=MessageResponse,
    summary="Register a doctor account",
    responses={
        409: {"model": ErrorEnvelope, "description": "Mobile or PRC license already registered"},
        **_RATE_LIMITED,
    },
)
async def sign_up_doctor(
    payload: DoctorSignUpRequest,
    request: Request,
    background: BackgroundTasks,
    sign_up: SignUpDoctorDep,
    mailer: MailerDep,
) -> MessageResponse:
    emails = await sign_up(payload.to_command(), client_ip=_client_ip(request))
    _send_later(background, mailer, emails)
    return MessageResponse(message=SIGNUP_MESSAGE)


@router.post(
    "/email-verification/confirm",
    response_model=MessageResponse,
    summary="Confirm an email verification token",
    responses={400: {"model": ErrorEnvelope, "description": "invalid_token or token_expired"}},
)
async def confirm_email(payload: ConfirmRequest, confirm: ConfirmEmailDep) -> MessageResponse:
    await confirm(payload.token)
    return MessageResponse(message=VERIFIED_MESSAGE)


@router.post(
    "/email-verification/resend",
    status_code=202,
    response_model=MessageResponse,
    summary="Send a new email verification link",
    responses=_RATE_LIMITED,
)
async def resend_verification(
    payload: ResendRequest,
    request: Request,
    background: BackgroundTasks,
    resend: ResendVerificationDep,
    mailer: MailerDep,
) -> MessageResponse:
    emails = await resend(payload.email, client_ip=_client_ip(request))
    _send_later(background, mailer, emails)
    return MessageResponse(message=RESEND_MESSAGE)


# --- Sessions (US-01.3) -----------------------------------------------------------------

FORGOT_MESSAGE = "If an account exists for this email, we've sent a reset link."
RESET_MESSAGE = "Your password has been reset. Sign in with your new password."
# Token responses must never be cached (RFC 6749 section 5.1).
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH * 4, repr=False)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return parse_email(value)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=200, repr=False)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105  (OAuth token type, not a secret)
    expires_in: int = Field(description="Access token lifetime in seconds")
    refresh_token: str
    refresh_expires_in: int = Field(description="Refresh token lifetime in seconds")

    @classmethod
    def of(cls, session: IssuedSession) -> "TokenResponse":
        return cls(
            access_token=session.access_token,
            expires_in=session.access_expires_in,
            refresh_token=session.refresh_token,
            refresh_expires_in=session.refresh_expires_in,
        )


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    new_password: str = Field(
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH * 4,
        repr=False,
        json_schema_extra={"format": "password"},
    )

    @field_validator("new_password")
    @classmethod
    def _password(cls, value: str) -> str:
        check_password_policy(value)
        return value


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in with email and password",
    responses={
        401: {"model": ErrorEnvelope, "description": "invalid_credentials"},
        403: {"model": ErrorEnvelope, "description": "email_not_verified"},
        **_RATE_LIMITED,
    },
)
async def login(
    payload: LoginRequest, request: Request, response: Response, sign_in: LoginDep
) -> TokenResponse:
    session = await sign_in(payload.email, payload.password, client_ip=_client_ip(request))
    response.headers.update(_NO_STORE)
    return TokenResponse.of(session)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a refresh token for a new token pair",
    responses={401: {"model": ErrorEnvelope, "description": "invalid_refresh_token"}},
)
async def refresh(
    payload: RefreshRequest, request: Request, refresh_session: RefreshSessionDep
) -> Response:
    result = await refresh_session(payload.refresh_token)
    if isinstance(result, RefreshRejected):
        # Returned, not raised: a revocation made on reuse must be committed with this response.
        error = InvalidRefreshTokenError()
        return error_response(request, status_code=401, code=error.code, message=error.message)
    return JSONResponse(TokenResponse.of(result).model_dump(), headers=_NO_STORE)


@router.post("/logout", status_code=204, summary="Sign out (revoke the refresh token's session)")
async def logout(payload: RefreshRequest, sign_out: LogoutDep) -> Response:
    await sign_out(payload.refresh_token)
    return Response(status_code=204)


@router.post(
    "/password/forgot",
    status_code=202,
    response_model=MessageResponse,
    summary="Email a password reset link",
    responses=_RATE_LIMITED,
)
async def forgot_password(
    payload: ResendRequest,
    request: Request,
    background: BackgroundTasks,
    request_reset: RequestPasswordResetDep,
    mailer: MailerDep,
) -> MessageResponse:
    emails = await request_reset(payload.email, client_ip=_client_ip(request))
    _send_later(background, mailer, emails)
    return MessageResponse(message=FORGOT_MESSAGE)


@router.post(
    "/password/reset",
    response_model=MessageResponse,
    summary="Set a new password with a reset token",
    responses={400: {"model": ErrorEnvelope, "description": "invalid_token or token_expired"}},
)
async def reset_password(payload: ResetPasswordRequest, reset: ResetPasswordDep) -> MessageResponse:
    await reset(payload.token, payload.new_password)
    return MessageResponse(message=RESET_MESSAGE)
