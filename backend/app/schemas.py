from datetime import date, datetime, time

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=1, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    tenant_id: int
    email: str
    role: str
    display_name: str

    model_config = {"from_attributes": True}


class PractitionerOut(BaseModel):
    id: int
    display_name: str
    user_id: int

    model_config = {"from_attributes": True}


class WeeklyHoursIn(BaseModel):
    practitioner_id: int
    weekday: int = Field(ge=0, le=6)
    start_time: time
    end_time: time


class WeeklyHoursOut(BaseModel):
    id: int
    practitioner_id: int
    weekday: int
    start_time: time
    end_time: time

    model_config = {"from_attributes": True}


class ExceptionIn(BaseModel):
    practitioner_id: int
    closed_on: date | None = None
    block_start: datetime | None = None
    block_end: datetime | None = None
    reason: str = ""


class ExceptionOut(BaseModel):
    id: int
    practitioner_id: int
    closed_on: date | None
    block_start: datetime | None
    block_end: datetime | None
    reason: str

    model_config = {"from_attributes": True}


class SlotOut(BaseModel):
    starts_at: datetime


class BookingIn(BaseModel):
    practitioner_id: int
    starts_at: datetime


class OnBehalfBookingIn(BaseModel):
    patient_id: int
    practitioner_id: int
    starts_at: datetime


class CancelIn(BaseModel):
    reason: str | None = None


class BookingOut(BaseModel):
    id: int
    practitioner_id: int
    patient_id: int
    starts_at: datetime
    status: str
    created_by_user_id: int
    cancelled_by_user_id: int | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    visit_record_id: int | None = None

    model_config = {"from_attributes": True}


class VisitOut(BaseModel):
    id: int
    booking_id: int
    notes: str
    updated_by_user_id: int | None
    updated_at: datetime | None
    patient_id: int
    practitioner_id: int
    starts_at: datetime
    booking_status: str
    cancelled_by_user_id: int | None
    cancelled_at: datetime | None
    cancel_reason: str | None


class VisitUpdateIn(BaseModel):
    notes: str


class DocumentOut(BaseModel):
    id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_by_user_id: int

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    event_type: str
    body: str
    read_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
