"""HS256 access tokens (PyJWT). Claims carry ids only: no email, name, or other personal data."""

import uuid
from datetime import timedelta

import jwt

from app.application.accounts.ports import Clock
from app.domain.accounts.entities import AccessClaims, IssuedAccessToken, User
from app.domain.accounts.values import Role
from app.domain.errors import NotAuthenticatedError

ISSUER = "recliniq"
AUDIENCE = "recliniq-api"
ALGORITHM = "HS256"
LEEWAY = timedelta(seconds=10)


class JwtTokenIssuer:
    def __init__(self, *, secret: str, ttl_minutes: int, clock: Clock) -> None:
        self._secret = secret
        self._ttl = timedelta(minutes=ttl_minutes)
        self._clock = clock

    def issue_access(self, user: User) -> IssuedAccessToken:
        now = self._clock.now()
        claims = {
            "sub": str(user.id),
            "role": user.role.value,
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + self._ttl,
            "jti": uuid.uuid4().hex,
        }
        token = jwt.encode(claims, self._secret, algorithm=ALGORITHM)
        return IssuedAccessToken(token=token, expires_in=int(self._ttl.total_seconds()))

    def decode_access(self, token: str) -> AccessClaims:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUER,
                leeway=LEEWAY,
                options={"require": ["sub", "role", "exp", "iat", "iss", "aud"]},
            )
            return AccessClaims(user_id=uuid.UUID(claims["sub"]), role=Role(claims["role"]))
        except (jwt.PyJWTError, ValueError, KeyError):
            raise NotAuthenticatedError from None
