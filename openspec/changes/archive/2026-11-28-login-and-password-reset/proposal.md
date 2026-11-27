## Why

Doctors can now sign up and verify their email (US-01.1), but they can't sign in. Every role-specific feature after this (RBAC in US-01.4, license review in US-01.6, schedules in US-02.1) needs an authenticated user. US-01.3 adds secure login, logout, and password reset. It also enforces the account states US-01.1 introduced: an email must be verified before login, while doctors whose license is still pending can log in and see that status.

**Sequencing:** stacked on US-01.1 (PR #9, not yet merged). This change reuses its users table, Argon2id hasher, Postgres rate limiter, mailer, and email templates.

## What Changes

- **Login**:
  - Email + password returns a short-lived **access token** (JWT, about 15 minutes) and a long-lived **refresh token** (opaque, about 30 days). Both are returned in the JSON body (product decision; see design for the XSS trade-off and its mitigations).
  - Wrong password and unknown email give the same `401 invalid_credentials`, and take similar time.
  - A correct password on an account whose email isn't verified gives `403 email_not_verified`. This is the only point where the client learns the account exists, and the page offers to resend the verification link.
  - Doctors with a pending or rejected license **can** log in.
  - Login attempts are rate-limited per IP and per email (`429` with `Retry-After`).
  - Password hashes are upgraded transparently on login when the hashing parameters change.
- **Refresh tokens are rotated**: each use returns a new pair and retires the old token. Presenting a retired token again (reuse) revokes the whole session (the token family). Only hashes of refresh tokens are stored.
- **Logout** revokes the session's refresh tokens. The access token remains valid until it expires (stateless JWT, at most about 15 minutes).
- **Current user**: `GET /api/v1/me` returns the signed-in user's profile, including role, email verification, and (for doctors) license status. It introduces the bearer-token authentication dependency that RBAC (US-01.4) will build on.
- **Forgot password**: always responds `202`. If the email belongs to an active account, a single-use reset link (1 hour, hashed) is emailed. Requests are rate-limited.
- **Reset password**:
  - The new password must meet the US-01.1 policy.
  - A successful reset uses up the link, invalidates other reset links, and **signs the user out everywhere** (revokes all refresh tokens).
  - It also marks the email as verified, since opening the link proves the user controls the address.
- **Frontend**:
  - `/login` (with the "verify your email first" + resend state), `/forgot-password`, `/reset-password`, and `/account` (profile plus a license status banner).
  - Header login/logout.
  - An auth layer that keeps the access token in memory, stores the refresh token, attaches `Authorization`, and refreshes once on `401`.

Out of scope: role enforcement on endpoints (US-01.4), idle timeout and 2FA (US-07.2), trusted-proxy IP handling (US-07.3), and "remember me" options.

## Capabilities

### New Capabilities
- `user-authentication`: login, access and refresh tokens (rotation and reuse detection), logout, the current-user endpoint, login rate limiting, the email-verified requirement, and the frontend login, logout, and account pages.
- `password-reset`: forgot-password requests, single-use expiring reset links, setting a new password, signing out everywhere after a reset, and the frontend forgot and reset pages.

### Modified Capabilities
- `email-verification`: the verify-email page's success state links to sign in. Separately, a completed password reset also marks the email as verified; that rule lives in the `password-reset` spec.

## Impact

- **Backend**:
  - Extends `accounts`: `Login`, `RefreshSession`, `Logout`, `RequestPasswordReset`, and `ResetPassword` services.
  - New ports: `TokenIssuer` (JWT) and `RefreshTokenRepository`.
  - A generalized single-use token repository, shared by verification and reset tokens.
  - A `CurrentUser` dependency, and new routes under `/api/v1/auth/...` plus `/api/v1/me`.
- **Database**: new `refresh_tokens` and `password_reset_tokens` tables. Both are soft-deletable and trigger-protected, with partial unique indexes on the token hashes. One Alembic revision.
- **Settings**: `JWT_SECRET` (required outside local/test, at least 32 bytes), `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS`, `PASSWORD_RESET_TTL_MINUTES`, and login and forgot-password rate limits. All are documented in `.env.example`, and Docker Compose sets a local secret.
- **Dependencies**: `PyJWT`.
- **Frontend**: an auth context/provider, API client changes for auth (bearer header plus one refresh retry), new pages and routes, and header changes.
- **Follow-ups**: US-01.4 adds role checks on top of `CurrentUser`. US-07.2 adds idle timeout. Consider moving the refresh token to an httpOnly cookie before launch if the XSS risk assessment changes.
