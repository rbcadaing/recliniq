"""Password policy (NIST SP 800-63B style): length and a blocklist, no composition rules."""

import unicodedata
from functools import cache
from pathlib import Path

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128

_COMMON_PASSWORDS_FILE = Path(__file__).with_name("common_passwords.txt")


@cache
def _common_passwords() -> frozenset[str]:
    lines = _COMMON_PASSWORDS_FILE.read_text(encoding="utf-8").splitlines()
    return frozenset(line for line in lines if line and not line.startswith("#"))


def normalize_password(password: str) -> str:
    return unicodedata.normalize("NFKC", password)


def check_password_policy(password: str, *, email: str | None = None) -> None:
    """Raise ValueError if the password breaks the policy. Never echoes the password."""
    normalized = normalize_password(password)
    if len(normalized) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(normalized) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"must be at most {MAX_PASSWORD_LENGTH} characters")
    if normalized.lower() in _common_passwords():
        raise ValueError("is too common; choose a less predictable password")
    if email is not None and normalized.lower() == email.strip().lower():
        raise ValueError("must not be your email address")
