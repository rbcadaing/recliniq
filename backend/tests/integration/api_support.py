"""Shared helpers for the account API integration tests (fixtures live in conftest.py)."""

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.accounts.mailer import InMemoryMailer
from app.infrastructure.accounts.models import UserModel

SIGNUP = "/api/v1/auth/doctors/signup"
CONFIRM = "/api/v1/auth/email-verification/confirm"
RESEND = "/api/v1/auth/email-verification/resend"
PASSWORD = "correct horse battery staple"
TOKEN_IN_LINK = re.compile(r"verify-email\?token=([\w-]+)")


class FakeClock:
    def __init__(self) -> None:
        self.current = datetime.now(UTC)

    def now(self) -> datetime:
        return self.current


def token_from(mailer: InMemoryMailer, index: int = -1) -> str:
    match = TOKEN_IN_LINK.search(mailer.outbox[index].text)
    assert match is not None
    return match.group(1)


async def user_row(session: AsyncSession, email: str = "juan.delacruz@example.com") -> UserModel:
    row = await session.scalar(select(UserModel).where(UserModel.email == email))
    assert row is not None
    return row


def field_errors(response: Any) -> set[str]:
    return {d["field"].split(".")[-1] for d in response.json()["error"]["details"]}
