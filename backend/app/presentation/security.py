"""Authentication dependency: ``CurrentUserDep`` resolves the signed-in user from a bearer token.

The user is reloaded on every request, so a soft-deleted account (or, later, a changed role)
takes effect immediately rather than when the access token expires. RBAC (US-01.4) builds on
this.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.accounts.entities import User
from app.domain.errors import NotAuthenticatedError
from app.presentation.dependencies import TokenIssuerDep, UserRepositoryDep

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Access token from POST /api/v1/auth/login",
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    issuer: TokenIssuerDep,
    users: UserRepositoryDep,
) -> User:
    if credentials is None:
        raise NotAuthenticatedError
    claims = issuer.decode_access(credentials.credentials)
    user = await users.find(claims.user_id)
    if user is None:
        raise NotAuthenticatedError
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
