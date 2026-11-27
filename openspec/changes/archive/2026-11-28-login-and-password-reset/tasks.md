## 1. Dependencies and settings

- [x] 1.1 Add `PyJWT` to `backend/pyproject.toml` and run `uv sync`. Verify that `uv run python -c "import jwt"` succeeds and that `uv.lock` is updated.
- [x] 1.2 Add the D7 settings to `app/core/config.py`, including the `JWT_SECRET` rule (dev default only in `local`/`test`; in `staging`/`production` it must be at least 32 bytes and not the default). Document each setting in `backend/.env.example`, add `JWT_SECRET` to the root `.env.example`, and pass it through `docker-compose.yml`. Verify with `tests/unit/test_config.py` cases: defaults; `production` with a missing, short, or default secret raises `ConfigError` naming `JWT_SECRET` without echoing the value; a valid production secret loads.

## 2. Domain and errors

- [x] 2.1 Add `InvalidCredentialsError` (401), `EmailNotVerifiedError` (403), `InvalidRefreshTokenError` (401), and `NotAuthenticatedError` (401, plus a `WWW-Authenticate: Bearer` header) to `app/domain/errors.py`, and map them in `presentation/errors.py`. Verify with an API unit test of each envelope and the header.
- [x] 2.2 Add domain types: `AccessClaims`, `IssuedAccessToken`, `RefreshToken` (with `family_id`, `used_at`, `revoked_at`), and `AccountProfile` (with an optional doctor section). Verify with `uv run mypy`.

## 3. Persistence

- [x] 3.1 Add the ORM models `RefreshTokenModel` and `PasswordResetTokenModel` (TimestampMixin + SoftDeleteMixin, `soft_unique_index` on `token_hash`, indexes on `user_id`/`family_id`). Generate the Alembic revision and add `protect_from_hard_delete` / `unprotect_from_hard_delete` for both tables. Verify that `alembic upgrade head` → `downgrade -1` → `upgrade head` succeeds, and that the drift check and soft-delete coverage tests pass.
- [x] 3.2 Generalize `SqlTokenRepository` into a base class parameterized by its model, with `SqlVerificationTokenRepository` and `SqlPasswordResetTokenRepository`. Update the US-01.1 wiring. Verify that the existing verification tests still pass, and add an integration test for the reset token lifecycle (add, find, mark used, invalidate unused).
- [x] 3.3 Implement `SqlRefreshTokenRepository` (`add`, `find_by_hash`, `mark_used`, `revoke_family`, `revoke_all_for_user`). Verify with integration tests for revoking a family versus all of a user's families and for finding used and revoked tokens.
- [x] 3.4 Extend `SqlUserRepository` with `update_password` and `find_profile` (joining doctor profile and specialization). Verify with integration tests for a doctor profile (`license_status`, specialization name) and a password update.

## 4. Adapters

- [x] 4.1 Implement `JwtTokenIssuer` (HS256 with `iss`, `aud`, `exp`, `iat`, `jti`, `sub`, `role`, and 10-second leeway). Verify with unit tests: round trip; expired, tampered, wrong-audience, and wrong-secret tokens are rejected; the claims contain no email or name.
- [x] 4.2 Add `needs_rehash` to `Argon2PasswordHasher` and the `PasswordHasher` port, and add the `password_reset_email` template. Verify with unit tests: a hash made with weaker parameters needs a rehash and a default one doesn't; the reset link has the form `{FRONTEND_BASE_URL}/reset-password?token=` and the HTML is escaped.

## 5. Application services

- [x] 5.1 Implement `Login` (D2): rate limit before the password check, one hash verify on every path using `DUMMY_HASH`, `invalid_credentials` vs `email_not_verified`, rehash on success, and issue a session. Verify with unit tests using fakes: success; wrong password and unknown email give the same error and each call verify exactly once; unverified with the right password gives `email_not_verified`; unverified with the wrong password gives `invalid_credentials`; a pending doctor succeeds; over the limit, no verify runs; an outdated hash is upgraded.
- [x] 5.2 Implement `RefreshSession` and `Logout` (D1). Verify with unit tests: rotation (the old token is used, the new one has the same family and the original expiry); reuse revokes the family, so the newest token fails; expired and unknown tokens are rejected; a revoked user's token is rejected; logout revokes the family and is idempotent.
- [x] 5.3 Implement `RequestPasswordReset` and `ResetPassword` (D3). Verify with unit tests: the same empty or non-empty outcome for unknown and known emails; a new request invalidates the older link; rate limited; reset updates the hash, uses up the token, revokes all families, and marks the email verified; used, unknown, and expired tokens give the right errors and leave the password unchanged.

## 6. API

- [x] 6.1 Add `presentation/security.py` with `CurrentUserDep` (`HTTPBearer`, decode, reload an active user) and `GET /api/v1/me`, and declare the bearer scheme in OpenAPI. Verify with integration tests: valid token gives the profile (a pending doctor shows `license_status: pending`); missing, expired, or tampered token gives 401 with `WWW-Authenticate`; a soft-deleted user's token gives 401.
- [x] 6.2 Add `POST /api/v1/auth/login`, `/auth/refresh`, and `/auth/logout`. Verify with integration tests covering every user-authentication login, refresh, and logout scenario: success; case-insensitive email; identical 401 bodies for wrong password and unknown email; 403 for unverified; 429 with `Retry-After`; refresh rotation; reuse revoking the newest token; idempotent logout (204).
- [x] 6.3 Add `POST /api/v1/auth/password/forgot` and `/auth/password/reset`. Verify with integration tests covering every password-reset scenario: identical 202 responses; the email is sent (`InMemoryMailer`); a weak password gives 422 and the token stays usable; success lets the user log in with the new password and not the old one; other sessions' refresh tokens fail; an unverified account becomes verified; used and expired links give the right codes; 429.
- [x] 6.4 Extend the OpenAPI unit test: the new paths with their 401, 403, 422, and 429 responses, the bearer security scheme, and `/me` requiring auth.

## 7. Frontend

- [x] 7.1 Add `src/auth/session.ts` (access token in memory; refresh token in `localStorage` with try/catch fallback; subscribe) and the `createApiClient` auth hooks (bearer header; one single-flight refresh and retry on 401 for non-`/auth/` paths; Web Locks across tabs with a fallback). Add `api/auth.ts` functions for login, refresh, logout, forgot, reset, and me. Verify with Vitest: the header is attached; a 401 triggers one refresh and a successful retry; concurrent 401s share one refresh; a failed refresh clears the session; `/auth/` paths are never retried; storage that throws doesn't crash.
- [x] 7.2 Add `AuthProvider` (restore on load, `login`, `logout`, `user` from the `['me']` query), `RequireAuth`, and the header changes in `Layout`. Verify with Vitest: restore with a stored refresh token signs in; logout clears storage, calls the backend, and goes to `/login`; the header switches between "Log in" and the user's name with "Log out".
- [x] 7.3 Build `/login`: field validation, `invalid_credentials` message, `email_not_verified` with resend for the typed email, 429 message, redirect to `state.from` or `/account`, and links to forgot password and sign-up. Verify with Vitest tests for each outcome.
- [x] 7.4 Build `/forgot-password` (always the same confirmation; 429), `/reset-password` (new password and confirmation, length check, 422 field error, `token_expired`/`invalid_token` with a link to request a new one, success links to login, no-referrer meta), and `/account` behind `RequireAuth` (profile and license banner: pending, rejected, approved). Add the "Sign in" link to the VerifyEmailPage success state. Verify with Vitest tests for each outcome, including the redirect to login and back for `/account`.
- [x] 7.5 Verify that `npm run lint && npm run typecheck && npm test -- --run && npm run build` passes.

## 8. End-to-end check and docs

- [x] 8.1 Manual check in the local stack:
  - log in as the verified doctor from US-01.1 and see `/account` showing "Pending verification";
  - reload the page and stay signed in;
  - log out;
  - use forgot password, open the email in Mailpit, reset, log in with the new password, and confirm the old password fails;
  - in Swagger, "Authorize" with an access token and call `/me`.
- [x] 8.2 Update `backend/README.md` (sessions: JWT, refresh rotation and reuse, `CurrentUserDep`, `JWT_SECRET` requirement), `CLAUDE.md` (the auth dependency, the token store, and the cross-tab refresh lock), and the root `README.md` (setting `JWT_SECRET` outside local). Verify by reading them.
- [x] 8.3 Verify that the full backend CI set passes: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest` (with `TEST_DATABASE_URL`).
