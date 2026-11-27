"""Argon2id password hashing. CPU-heavy work runs in a worker thread, off the event loop."""

import anyio.to_thread
from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerificationError

from app.domain.accounts.passwords import normalize_password


class Argon2PasswordHasher:
    def __init__(self) -> None:
        self._argon2 = _Argon2()  # library defaults: Argon2id with RFC 9106 parameters

    async def hash(self, password: str) -> str:
        normalized = normalize_password(password)
        return await anyio.to_thread.run_sync(self._argon2.hash, normalized)

    async def verify(self, password_hash: str, password: str) -> bool:
        normalized = normalize_password(password)

        def _verify() -> bool:
            try:
                return self._argon2.verify(password_hash, normalized)
            except (VerificationError, InvalidHashError):
                return False

        return await anyio.to_thread.run_sync(_verify)
