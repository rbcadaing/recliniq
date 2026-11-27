"""Account value types and parsers. Pure Python: each parser normalizes or raises ValueError.

Pydantic request schemas call these parsers, so a ValueError becomes a 422 naming the field.
"""

import re
from enum import StrEnum

from email_validator import EmailNotValidError, validate_email


class Role(StrEnum):
    DOCTOR = "doctor"
    PATIENT = "patient"
    STAFF = "staff"
    ADMIN = "admin"


class LicenseStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


MAX_EMAIL_LENGTH = 254
PRC_LICENSE_LENGTH = 7

_MOBILE_SEPARATORS = re.compile(r"[\s\-]")
# 09XXXXXXXXX, 639XXXXXXXXX or +639XXXXXXXXX (Philippine mobile numbers start with 9).
_PH_MOBILE = re.compile(r"^(?:\+?63|0)(9\d{9})$")
_PRC_LICENSE = re.compile(r"^\d{1,7}$")


def parse_email(raw: str) -> str:
    """Return the address in lowercase, or raise ValueError."""
    candidate = raw.strip()
    if len(candidate) > MAX_EMAIL_LENGTH:
        raise ValueError(f"must be at most {MAX_EMAIL_LENGTH} characters")
    try:
        result = validate_email(candidate, check_deliverability=False)
    except EmailNotValidError:
        raise ValueError("must be a valid email address") from None
    return result.normalized.lower()


def parse_ph_mobile(raw: str) -> str:
    """Return the number in E.164 form (+639XXXXXXXXX), or raise ValueError."""
    match = _PH_MOBILE.match(_MOBILE_SEPARATORS.sub("", raw.strip()))
    if match is None:
        raise ValueError("must be a Philippine mobile number, e.g. 0917 123 4567")
    return f"+63{match.group(1)}"


def parse_prc_license(raw: str) -> str:
    """Return the PRC license number zero-padded to 7 digits, or raise ValueError."""
    candidate = raw.strip()
    if _PRC_LICENSE.match(candidate) is None:
        raise ValueError("must be 1 to 7 digits")
    return candidate.zfill(PRC_LICENSE_LENGTH)
