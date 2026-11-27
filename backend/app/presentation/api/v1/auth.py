"""Public account endpoints: doctor sign-up and email verification."""

import uuid
from typing import Annotated, Any, Self

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.application.accounts.ports import EmailMessage, Mailer
from app.application.accounts.services import DoctorSignUp
from app.domain.accounts.passwords import MAX_PASSWORD_LENGTH, check_password_policy
from app.domain.accounts.values import parse_email, parse_ph_mobile, parse_prc_license
from app.presentation.dependencies import (
    ConfirmEmailDep,
    MailerDep,
    ResendVerificationDep,
    SignUpDoctorDep,
)
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
