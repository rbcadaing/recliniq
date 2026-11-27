## Context

See proposal.md for motivation and `specs/` for the required behavior.

Current state, on the stacked US-01.1 branch:
- The `accounts` feature already follows ports and adapters: `UserRepository`, `TokenRepository` (verification tokens, soft-deleted to invalidate), `PasswordHasher` (Argon2id), `Mailer`, `RateLimiter` (Postgres fixed window, own transaction), and `Clock`.
- Services return the emails to send, and routes deliver them with `BackgroundTasks`.
- Error envelope: `AppError` subclasses map to statuses in `presentation/errors.py`, and `RateLimitedError` adds `Retry-After`.
- Frontend: `api` client (`get`/`post`, `ApiError` with `retryAfter`), TanStack Query, and `src/features/accounts/` (form helpers, validators, `ResendVerification`). Tests use `renderAt` + `mockApi`.

## Goals / Non-Goals

**Goals:**
- A `CurrentUser` dependency and token model that US-01.4 (RBAC) can build on without changes.
- Sessions that are safe even though the refresh token is readable by JavaScript (product decision): rotation, reuse detection, and short-lived access tokens.
- Login and reset flows that reveal nothing about which emails exist, except `email_not_verified` after a correct password.

**Non-Goals:**
- Role checks on endpoints (US-01.4).
- Idle timeout and 2FA (US-07.2).
- Revoking access tokens before they expire.
- Listing or managing sessions per device.

## Decisions

### D1. Token model: stateless JWT access token plus a stored, rotating refresh token

```
login ──▶ access JWT (15 min, HS256)          refresh token (opaque, 30 days)
          claims: sub, role, iat, exp,         random 256-bit; DB stores sha256 only
                  iss=recliniq, aud=api, jti   refresh_tokens: family_id, used_at, revoked_at

refresh(T1) ─▶ T1.used_at=now, issue T2 (same family) + new access JWT
refresh(T1) again ─▶ T1 already used ⇒ REUSE ⇒ revoke whole family (T2 dies too) ⇒ 401
logout(Tn)  ─▶ revoke whole family ⇒ 204 (unknown/revoked ⇒ still 204)
reset password ─▶ revoke ALL families of the user
```

- The access token is a JWT signed with HS256 using `JWT_SECRET` (PyJWT). Decoding checks signature, `exp`, `iss`, and `aud`, and allows a small 10-second clock skew. `role` is included for RBAC later, but `CurrentUser` always reloads the user (D4). That way a deleted user, or a role changed by an admin, takes effect on the next request rather than at token expiry.
- The refresh token is opaque, not a JWT, so it can be revoked and hashing it is enough. The `refresh_tokens` table:
  - columns: `id`, `user_id`, `family_id`, `token_hash`, `expires_at`, `used_at`, `revoked_at`, plus timestamps and soft delete;
  - a partial unique index on `token_hash`, and a trigger.
- Revocation uses `revoked_at`, not soft delete. Reuse detection has to *find* used tokens, and explicit columns make what happened readable in audits.
- **Revocations must survive the 401.** When reuse is detected, the family is revoked *and* the response is 401. Raising an error would roll back the request's unit of work and undo the revocation. So `RefreshSession` *returns* `RefreshRejected` instead of raising, and the route writes the 401 envelope itself, which lets the session commit. An integration test checks this through the real (non-overridden) database session.
- The new token keeps the family's original `expires_at` (sliding is *not* used). Every session must sign in again within 30 days, whatever its activity.

*Alternative considered:* refresh token in an httpOnly cookie. This was recommended, but the product chose JSON bodies (simpler now, and ready for mobile clients). The risk and mitigations are in Risks.

### D2. Login flow

```
POST /api/v1/auth/login {email, password}
  │ parse_email (422 if malformed)
  │ rate limit login:ip, login:email ──over──▶ 429 (password NOT checked)
  │ user = find_by_email(email)
  │ ok = verify(user.hash if user else DUMMY_HASH, password)   ← always one Argon2 verify
  │ not user or not ok ──▶ 401 invalid_credentials
  │ not user.email_verified ──▶ 403 email_not_verified
  │ needs_rehash(user.hash) ──▶ update_password(hash(password))
  ▼ issue access JWT + new refresh family ──▶ 200
```

- `DUMMY_HASH` is computed once, lazily, with the same parameters, so unknown emails cost one Argon2 verify like known ones.
- The rate limit counts **every** attempt, not only failures. That's simpler, and the limits are generous: 30 per IP and 10 per email per 15 minutes. There's no account lockout, which would let attackers lock out real users. Login uses its own window setting (15 minutes), separate from the sign-up window (1 hour).
- `PasswordHasher` gains `needs_rehash(hash) -> bool` (argon2-cffi `check_needs_rehash`).

### D3. Password reset flow
- `POST /auth/password/forgot {email}`:
  - rate limit (`forgot:ip` / `forgot:email`);
  - if there's an active account (verified or not), invalidate its earlier reset tokens (soft delete) and issue a new one: random 256-bit, sha256 stored, 60-minute TTL;
  - return the email for `BackgroundTasks`. The response is always 202.
- `POST /auth/password/reset {token, new_password}`:
  - The Pydantic schema runs the password policy first, so a weak password is a 422 and leaves the token unused.
  - The service then looks up the token by hash: unknown or used → `invalid_token`, expired → `token_expired`.
  - On success, in one transaction: set the new hash, mark the token used, invalidate other reset tokens, revoke all refresh families, and set `email_verified_at` if it's null.
- Generalize the single-use token repository. `SqlTokenRepository` becomes a base class parameterized by its model, with `SqlVerificationTokenRepository` and `SqlPasswordResetTokenRepository` as subclasses. Both implement the existing `TokenRepository` port. `password_reset_tokens` has the same shape as `email_verification_tokens`.
- A new `password_reset_email` template links to `{FRONTEND_BASE_URL}/reset-password?token=...`. The token in the URL is a known risk for referrer and history leakage; it's limited by the single use and 60-minute TTL, and the page sets `<meta name="referrer" content="no-referrer">`.

### D4. CurrentUser dependency (the base for RBAC)
- `presentation/security.py`:
  - `HTTPBearer(auto_error=False)` reads the token, and `TokenIssuer.decode_access()` returns the claims or raises.
  - Then `users.find(sub)` must return an active user.
  - Any failure raises `NotAuthenticatedError` (401, code `not_authenticated`). The error handler adds `WWW-Authenticate: Bearer`.
  - Exposed as `CurrentUserDep`. US-01.4 will add `require_role(...)` on top.
- `GET /api/v1/me` returns `AccountProfile`: id, first, middle, and last name, email, role, email_verified, and for doctors a `doctor: {specialization: {id, name}, license_status}` object. It's served by a new `UserRepository.find_profile(user_id)`, which joins `doctor_profiles` and `specializations`.
- OpenAPI declares the bearer security scheme, so Swagger's "Authorize" button works for manual testing.

### D5. New errors
| Error | Status | Code |
|---|---|---|
| `InvalidCredentialsError` | 401 | `invalid_credentials` |
| `EmailNotVerifiedError` | 403 | `email_not_verified` |
| `InvalidRefreshTokenError` | 401 | `invalid_refresh_token` |
| `NotAuthenticatedError` | 401 | `not_authenticated` (+ `WWW-Authenticate: Bearer`) |

The existing `InvalidTokenError` and `TokenExpiredError` (400) are reused for reset links.

### D6. Ports and layering (extends US-01.1)
- New ports:
  - `TokenIssuer`: `issue_access(user) -> IssuedAccessToken(token, expires_in)` and `decode_access(token) -> AccessClaims`.
  - `RefreshTokenRepository`: `add`, `find_by_hash`, `mark_used`, `revoke_family`, `revoke_all_for_user`.
- Extended ports: `UserRepository` gains `update_password` and `find_profile`, and `PasswordHasher` gains `verify` (exists) and `needs_rehash`.
- New services in `application/accounts/sessions.py`: `Login`, `RefreshSession`, `Logout`, `RequestPasswordReset`, `ResetPassword`. A shared `_issue_session(user, family_id=None)` creates the token pair.
- Adapters: `JwtTokenIssuer` (`infrastructure/accounts/jwt.py`), `SqlRefreshTokenRepository`, and the generalized token repositories.

### D7. Settings (documented in `backend/.env.example`, set in compose)
- `JWT_SECRET` is a `SecretStr`.
  - In `local` and `test`, it defaults to a clearly marked dev value.
  - In `staging` and `production`, config validation **fails** if it's missing, shorter than 32 bytes, or equal to the dev default. This is a `ConfigError` naming the setting without echoing the value.
  - Docker Compose passes `JWT_SECRET` from the root `.env`, which has a local placeholder.
- `ACCESS_TOKEN_TTL_MINUTES=15`, `REFRESH_TOKEN_TTL_DAYS=30`, `PASSWORD_RESET_TTL_MINUTES=60`.
- `RATE_LIMIT_LOGIN_WINDOW_SECONDS=900`, `RATE_LIMIT_LOGIN_PER_IP=30`, `RATE_LIMIT_LOGIN_PER_EMAIL=10`.
- `RATE_LIMIT_FORGOT_PER_IP=10` and `RATE_LIMIT_FORGOT_PER_EMAIL=3`, using the existing 1-hour window.

### D8. Frontend session layer
- `src/auth/session.ts` is a tiny store:
  - The access token and its expiry are kept in a module variable, **memory only**.
  - The refresh token is in `localStorage` (`recliniq.refreshToken`), with every access wrapped in try/catch. If storage is unavailable, it falls back to memory only, so the session doesn't survive a reload.
  - It provides `subscribe` for React.
- API client: `createApiClient(baseUrl, fetchImpl, auth?)` takes optional hooks `{ getAccessToken, refresh }`.
  - It adds `Authorization: Bearer` when a token exists.
  - On a 401 from a non-`/auth/` path, it awaits `refresh()` **once**, shared by concurrent requests (single-flight), and retries once.
  - `api` is wired to the session store, so existing calls are unchanged.
- **Refreshing across tabs:** tabs share `localStorage`, so two tabs could refresh with the same token at once. The second request would look like reuse and kill the session (D1). To prevent this, `refresh()` runs inside `navigator.locks.request('recliniq-refresh', ...)`. After taking the lock, it re-reads `localStorage`. If another tab already rotated the token, it uses the new one instead of calling the API. Where Web Locks isn't available (tests, old browsers), it falls back to the in-tab single-flight only.
- `AuthProvider` (context):
  - On start, if a refresh token is stored, it calls refresh, then loads `/me` with TanStack Query (`['me']`).
  - It exposes `user`, `status` (`loading | signedIn | signedOut`), `login(email, password)`, and `logout()`.
  - `logout` calls the backend (and ignores network errors), clears the store and the query cache, and goes to `/login`.
- `RequireAuth` wraps protected routes. While loading it shows a spinner; when signed out it redirects to `/login` with `state.from`.
- Pages:
  - `LoginPage` handles `invalid_credentials`, `email_not_verified` (with `ResendVerification` for the typed email), and 429.
  - `ForgotPasswordPage` always shows the same confirmation.
  - `ResetPasswordPage` reads the token and takes a new password with confirmation and a length check. It handles 422 field errors, `token_expired`, and `invalid_token`, and sets no-referrer.
  - `AccountPage` shows the profile and a license banner: pending, rejected, or approved.
- Layout header: signed out shows "Log in" and "Sign up as a doctor"; signed in shows the user's name (linking to `/account`) and "Log out". The `VerifyEmailPage` success state gets a "Sign in" link.

## Risks / Trade-offs

- [The refresh token sits in `localStorage`, so XSS can steal it] → Mitigations:
  - rotation with reuse detection, so a stolen token used after the real client revokes the session, and vice versa;
  - a 30-day absolute expiry;
  - a 15-minute access token kept in memory only;
  - React escapes output by default, and there's no `dangerouslySetInnerHTML`.

  Follow-ups: add a strict Content-Security-Policy at deployment, and reconsider moving the refresh token to an httpOnly cookie before handling real patient data.
- [Logged-out access tokens work for up to 15 minutes] → accepted for stateless JWTs. The short TTL limits it, and `CurrentUser` reloads the user, so deleted accounts stop immediately.
- [Rate limits count successful logins too] → the limits are high enough for real users. Counting only failures would need a peek-then-hit flow; revisit if it causes support issues.
- [Reset token in the URL] → single use, 60-minute TTL, and no-referrer on the page.
- [HS256 means every verifier holds the signing secret] → there's a single backend today. Move to asymmetric keys (EdDSA or RS256) if other services ever need to verify tokens.
- [The `JWT_SECRET` dev default leaks into production] → config fails at startup outside local and test (tested).
- [Concurrent refresh in one tab] → in-tab single-flight. Across tabs → Web Locks plus re-reading storage.

## Migration Plan

- One Alembic revision creates `refresh_tokens` and `password_reset_tokens`, with indexes on `user_id` and `family_id`, partial unique indexes on `token_hash`, and `protect_from_hard_delete` on both. The downgrade reverses it. The US-00.2 coverage tests check both tables automatically.
- Deploy notes: set `JWT_SECRET` (32+ random bytes) in every non-local environment before deploying. Rotating it signs everyone out of their access tokens, but refresh tokens keep working.
- Rollback: `alembic downgrade -1`. Tokens already issued become useless, and users simply sign in again.

## Open Questions

- Exact wording for the login, reset, and account pages and the reset email, which can be refined in review.
