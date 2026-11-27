## 1. Dependencies, settings, and local mail

- [x] 1.1 Add `argon2-cffi`, `aiosmtplib`, and `email-validator` to `backend/pyproject.toml` and run `uv sync`. Verify that `uv run python -c "import argon2, aiosmtplib, email_validator"` succeeds and that `uv.lock` is updated.
- [x] 1.2 Add the D10 settings to `app/core/config.py` with defaults, and document each in `backend/.env.example`. Verify with unit tests in `tests/unit/test_config.py` for the defaults and for parsing an override.
- [x] 1.3 Add a pinned `mailpit` service to `docker-compose.yml` (SMTP 1025, UI 8025) and point the backend at it (`SMTP_HOST=mailpit`, `FRONTEND_BASE_URL`). Add `MAILPIT_UI_PORT` to the root `.env.example`, and add the Mailpit URL to the README service table. Verify that `docker compose up --build` starts all four services and that `http://localhost:8025` loads.

## 2. Domain (pure Python)

- [x] 2.1 Create `app/domain/accounts/` with the `Role` and `LicenseStatus` enums and value objects that parse and normalize `EmailAddress` (lowercase, at most 254 characters), `PhMobileNumber` (to E.164 `+639XXXXXXXXX`), and `PrcLicenseNumber` (1–7 digits, zero-padded to 7). Verify with parametrized unit tests covering every accepted and rejected example in the doctor-registration spec.
- [x] 2.2 Add the password policy: 12–128 characters after NFKC normalization, not on `common_passwords.txt`, and not equal to the email. Bundle the roughly 10k-entry list. Verify with unit tests for too short, too long, a common password, equal to the email, and an accepted passphrase.
- [x] 2.3 Add the domain errors `InvalidTokenError` (`invalid_token`) and `TokenExpiredError` (`token_expired`), and a field-aware `ConflictError` usage that puts the field in `details`. Map the token errors to 400 in `presentation/errors.py`. Verify with an API unit test of both envelopes.

## 3. Persistence

- [x] 3.1 Add ORM models in `app/infrastructure/accounts/models.py`: `Specialization`, `User`, `DoctorProfile`, and `EmailVerificationToken`, all with `TimestampMixin` + `SoftDeleteMixin`, plus the `CHECK` constraints and `soft_unique_index`es from D1. Also add `RateLimitCounter`, registered in `SOFT_DELETE_EXEMPT_TABLES` with a reason comment. Import them in `app/infrastructure/db/models.py`. Verify that the US-00.2 metadata coverage test passes.
- [x] 3.2 Generate the Alembic revision. Add `protect_from_hard_delete()` for every table except `rate_limit_counters`, and seed the specializations with fixed UUIDs (D8). Downgrade reverses everything. Verify that `alembic upgrade head` → `downgrade -1` → `upgrade head` succeeds, and that the drift check and the trigger-coverage integration test pass.
- [x] 3.3 Implement repositories on `SoftDeleteRepository`: users (by email, mobile; add), doctor profiles (by PRC), specializations (list, get), and tokens (by hash, add, invalidate unused for user via soft delete). Map `IntegrityError` constraint names to field conflicts. Verify with integration tests, including that reuse is allowed after an account is soft-deleted.
- [x] 3.4 Implement `PostgresRateLimiter` (D2): an atomic upsert counter keyed by hashed bucket, `Retry-After` computed from the window end, and opportunistic purging of old windows. Verify with integration tests showing the limit is reached, the counter resets in the next window (using an injected clock), and no raw IP or email is stored.

## 4. Adapters

- [x] 4.1 Implement `Argon2PasswordHasher` (Argon2id, run in a worker thread). Verify with unit tests that the hash verifies, differs from the password, and differs between two hashes of the same password.
- [x] 4.2 Implement `SmtpMailer` (aiosmtplib), `InMemoryMailer`, and the email templates (verification link, "account already exists" notice). Logs mask the address and never include the token. Verify with unit tests of the templates (link format `{FRONTEND_BASE_URL}/verify-email?token=`), and of `SmtpMailer` against a fake SMTP server or with `aiosmtplib` mocked, including that a send failure is logged rather than raised.

## 5. Application services

- [x] 5.1 Define the ports in `app/application/accounts/ports.py` (UserRepository, SpecializationRepository, TokenRepository, PasswordHasher, Mailer, RateLimiter, Clock). Implement `SignUpDoctor`: rate limit, then policy, then hash, then the duplicate-email branch, then 409s for mobile and PRC, then create the user, profile, and token, then return the outbox emails. Verify with unit tests using in-memory fakes for every branch in D4.
- [x] 5.2 Implement `ConfirmEmail` (valid, used, expired, unknown) and `ResendVerification` (unverified, which invalidates older tokens; unknown or verified, which sends nothing; rate limited). Verify with unit tests using fakes and a fixed clock.

## 6. API

- [x] 6.1 Add `GET /api/v1/specializations` and wire the dependencies in `presentation/dependencies.py`. Verify with an integration test that the list is non-empty and sorted by name.
- [x] 6.2 Add `POST /api/v1/auth/doctors/signup` with Pydantic schemas that call the domain value objects (422 field names match the spec), returning 202 and sending emails through `BackgroundTasks`, with 409 and 429 (`Retry-After`). Verify with integration tests for every doctor-registration scenario (happy path, each 422, the 409s, duplicate email verified and unverified with identical responses, 429 per IP and per email, consent recorded, password hash not equal to the password, and the password absent from captured logs). The tests use `InMemoryMailer`.
- [x] 6.3 Add `POST /api/v1/auth/email-verification/confirm` and `/resend`. Verify with integration tests for every email-verification scenario (valid, reused, expired, unknown, resend invalidates old links, identical 202 for unknown or verified, 429, and that a mail failure still returns 202).
- [x] 6.4 Verify that the OpenAPI document lists the new endpoints with their request and response schemas and the 409, 422, and 429 envelopes (extend `test_openapi_document_lists_v1_endpoints`).

## 7. Frontend

- [x] 7.1 Add `post<T>()` to `api/client.ts`, and expose `retryAfter` (from the `Retry-After` header) on `ApiError`. Add `api/auth.ts` and `api/specializations.ts`. Verify with `client.test.ts` cases for POST bodies and `retryAfter`.
- [x] 7.2 Add client-side validators in `src/features/accounts/validation.ts` that mirror the backend rules (PH mobile, PRC, email, password length, consent). Verify with Vitest cases matching the backend examples.
- [x] 7.3 Build `/signup/doctor`: the form, a specialization select, a link to the privacy notice, and the mapping of backend 422/409 field errors and 429 messages. On success, navigate to `/signup/check-email` with the email. Verify with Vitest/Testing Library tests for client-side errors, a backend field error keeping the entered values, and navigation on success (mocked API).
- [x] 7.4 Build `/signup/check-email` (resend button with success and 429 states), `/verify-email` (confirm on mount, showing verified, expired with resend, or invalid with resend), and a placeholder `/privacy` page showing the notice version. Verify with Vitest tests for each outcome.
- [x] 7.5 Verify that `npm run lint && npm run typecheck && npm test -- --run && npm run build` passes.

## 8. End-to-end check and docs

- [x] 8.1 Manual check in the local stack: sign up at `http://localhost:5173/signup/doctor`, open the email in Mailpit (`http://localhost:8025`), follow the link, and see "verified". Confirm in the database that `email_verified_at` is set, `license_status = 'pending'`, and the stored mobile and PRC values are normalized.
- [x] 8.2 Update `backend/README.md` (the accounts feature, the ports and adapters pattern, and the rate limiter), the root `README.md` (Mailpit URL), and `CLAUDE.md` (Mailpit, the rate-limit exemption, and the accounts layering). Verify by reading them.
- [x] 8.3 Verify that the full backend CI set passes: `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest` (with `TEST_DATABASE_URL`).
