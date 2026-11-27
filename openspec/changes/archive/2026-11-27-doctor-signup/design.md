## Context

See proposal.md for motivation and `specs/` for the required behavior.

Current state:
- The backend has clean-architecture layers and an error envelope. US-00.2 added soft delete: `SoftDeleteMixin`, session-wide filtering and guards, `SoftDeleteRepository`, `protect_from_hard_delete()`, `soft_unique_index()`, and the `SOFT_DELETE_EXEMPT_TABLES` list.
- The frontend has React Router, TanStack Query, and an `api` client that only has `get` today.
- No tables, auth, or outbound email exist yet. This is the first feature that uses ports and adapters for real, so the patterns it sets will be copied by US-01.2 and US-01.3.

## Goals / Non-Goals

**Goals:**
- An account model that patient sign-up (US-01.2), login (US-01.3), and RBAC (US-01.4) can extend without reshaping it.
- Reusable building blocks: password hashing, verification tokens, the mailer, and rate limiting.
- Sign-up responses shouldn't reveal registered emails, either through response bodies or obvious timing differences.

**Non-Goals:**
- Sessions and tokens (JWT), and enforcing "verified before login" (US-01.3).
- Admin license review endpoints and UI (separate story); the review columns are created now but stay empty.
- SMS verification, PRC ID upload, the license expiry date, and the privacy notice's actual content (US-07.1). This change ships a placeholder `/privacy` page with a version string.

## Decisions

### D1. Data model: `users` plus a 1:1 `doctor_profiles`

```
users                                   doctor_profiles (PK/FK user_id → users.id)
  id uuid PK                              specialization_id → specializations.id
  email (lowercase)                       prc_license_no char(7)
  mobile (E.164)                          license_status  pending|approved|rejected
  password_hash                           license_reviewed_at / _by / license_review_note (null)
  first_name, middle_name?, last_name   specializations
  role  doctor|patient|staff|admin        id uuid PK, code (slug), name
  email_verified_at?                    email_verification_tokens
  privacy_consent_at                      id, user_id → users.id, token_hash (sha256 hex)
  privacy_notice_version                  expires_at, used_at?
  + TimestampMixin + SoftDeleteMixin    rate_limit_counters   (soft-delete EXEMPT)
                                          bucket text, window_start timestamptz, count int
                                          PK (bucket, window_start)
```

- All tables use `TimestampMixin` and `SoftDeleteMixin`, and their migration calls `protect_from_hard_delete()`. The only exception is `rate_limit_counters`.
- Uniqueness uses `soft_unique_index`, for: `users.email`, `users.mobile`, `doctor_profiles.prc_license_no`, `specializations.code`, and `email_verification_tokens.token_hash`.
- `role` and `license_status` are `String` columns with `CHECK` constraints, not native PG enums. Adding a value later is then a constraint swap, not `ALTER TYPE`.
- Email uniqueness is on the lowercased value. The application lowercases emails, and the column has a `CHECK (email = lower(email))`. This avoids `citext` and functional indexes.
- Profile-specific data stays out of `users`, so patient data (US-01.2) can go in `patient_profiles` alongside it.

*Alternative considered:* one wide `users` table with nullable doctor columns. Rejected: it mixes roles and makes the PRC partial unique index awkward.

### D2. Rate-limit counters in Postgres, exempt from soft delete
- The table uses fixed windows: `INSERT ... ON CONFLICT (bucket, window_start) DO UPDATE SET count = count + 1 RETURNING count`. That's one round trip and atomic.
- The bucket key is `"{action}:{kind}:{sha256(value)}"`, for example `signup:ip:<hash>`. Raw IPs and emails are never stored.
- `Retry-After` is the number of seconds until the window ends.
- The table goes on `SOFT_DELETE_EXEMPT_TABLES`, with the reason recorded in a comment: operational counters with no business meaning, which must be purged. It is not protected by the trigger.
- Old windows are purged opportunistically. About 1% of increments also delete windows older than 1 day. There's no scheduler yet.
- The window and limits are settings:
  - sign-up: 5 per IP per hour and 3 per email per hour;
  - resend: 10 per IP per hour and 3 per email per hour.
- The client IP is `request.client.host`. Handling a reverse proxy (`X-Forwarded-For` with trusted proxies) is deferred to deployment work and noted as a risk.

The application port `RateLimiter.hit(bucket, limit, window) -> RateLimitDecision` keeps the storage swappable, so Redis remains an option later.

### D3. Password hashing with `argon2-cffi`, off the event loop
- `Argon2PasswordHasher` implements the `PasswordHasher` port with the library's default Argon2id parameters.
- `hash()` runs in `anyio.to_thread.run_sync`, so hashing doesn't block other requests.
- Policy checks live in the domain as pure functions: length after NFKC normalization, the common-password list, and "not equal to the email". The list is about 10k entries shipped as a text file at `app/domain/accounts/common_passwords.txt` and loaded once. The policy runs before uniqueness checks.

### D4. Sign-up flow and the duplicate-email path

```
POST /api/v1/auth/doctors/signup
  │ validate (pydantic + domain) ──bad──▶ 422
  │ rate limit (ip, email) ──over──▶ 429
  │ specialization unknown? ──▶ 422      ┐ every non-202 outcome is decided BEFORE the
  │ mobile / PRC taken? ──▶ 409 field    ┘ email lookup, so it never depends on the email
  │ hash password (always → similar timing on both email paths)
  │ email exists among active users?
  │   ├─ no:  insert user + profile + token ──▶ outbox: verification email
  │   └─ yes: unverified → invalidate old links, new token; outbox: verification email
  │           verified   → outbox: "account exists" notice
  ▼ commit ──▶ 202 {"message": "..."} ──▶ background: send outbox emails
```

- The service returns the emails to send. The route schedules them with FastAPI `BackgroundTasks`, which run after the response is sent. Delivery doesn't hold up the response, can't fail the request, and the two paths look the same from the outside.
- Mobile and PRC conflicts are checked for **every** sign-up, before the email lookup. Checking them only for new emails would leak email registration: submit a known email with a taken mobile number, and the response would be 202 if the email exists but 409 if it doesn't. As a side effect, someone re-submitting their own details gets a 409 on mobile rather than the "account exists" email. That's acceptable, since it tells them they already have an account.
- Mobile and PRC conflicts return 409, a deliberate trade-off. PRC numbers are public (anyone can look them up on the PRC website), and a mobile conflict needs a clear message to be usable. Hiding only email existence protects the main sign-in identifier.
- Two concurrent sign-ups can race on a unique value. The partial unique index rejects one, and its `IntegrityError` is mapped by constraint name to the same 409 or the duplicate-email path.

*Alternative considered:* a durable outbox table with a worker. Deferred: no worker infrastructure exists yet, and a lost email is recoverable through resend (see the email-verification spec on delivery failures).

### D5. Verification tokens
- Tokens are `secrets.token_urlsafe(32)`, and only `sha256(token)` is stored. A slow hash isn't needed: the token has 256 bits of entropy.
- Confirmation is `POST /api/v1/auth/email-verification/confirm {token}`. The token is looked up by hash, and the outcome is one of:
  - not found or already used → `invalid_token`;
  - expired → `token_expired`;
  - otherwise set `used_at` and `users.email_verified_at`.
- Earlier tokens are **invalidated by soft-deleting them** (system actor). This reuses US-00.2 semantics, and default queries then ignore them automatically.
- Resend is `POST /api/v1/auth/email-verification/resend {email}` and always returns 202.
- The link is `{FRONTEND_BASE_URL}/verify-email?token=...`. The page sends the `POST`, so `GET` prefetching by mail scanners does nothing.
- `InvalidTokenError` and `TokenExpiredError` are new `AppError` subclasses mapped to 400.
- Field names in error details: request validation (422) uses FastAPI's `body.<field>`, while service-level errors (409, unknown specialization 422) use the bare `<field>`. The frontend matches errors to inputs by the last segment of the name.

### D6. Mailer port and adapters
- The `Mailer.send(message: EmailMessage)` port takes `to`, `subject`, `text`, and `html`.
- Adapters:
  - `SmtpMailer` (aiosmtplib) is the default. Settings: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD` (optional), `SMTP_STARTTLS`, `MAIL_FROM`.
  - `InMemoryMailer` is used in tests through a dependency override and keeps an outbox list.
- Templates are small Python functions that return a subject plus text and HTML. No template engine yet.
- Logging masks the address (`j***@example.com`) and never logs the token.
- Docker Compose adds `mailpit` (pinned `axllent/mailpit` tag) with SMTP on 1025 and a web UI on 8025, and the backend env points `SMTP_HOST=mailpit`. CI doesn't need SMTP, because the tests use the in-memory mailer.

### D7. Layering

```
domain/accounts/        User, DoctorProfile, Role, LicenseStatus, EmailAddress/Mobile/PrcLicense
                        value objects (parse + normalize), password policy, errors
application/accounts/   SignUpDoctor, ConfirmEmail, ResendVerification services;
                        ports: UserRepository, SpecializationRepository, TokenRepository,
                        PasswordHasher, Mailer, RateLimiter, Clock
infrastructure/accounts/ ORM models + repositories (SoftDeleteRepository), Argon2 hasher,
                        SmtpMailer/InMemoryMailer, PostgresRateLimiter
presentation/api/v1/    auth.py (signup, confirm, resend), specializations.py; schemas
```

- The ORM models are separate from the domain entities, and repositories map between them. This keeps `domain/` free of SQLAlchemy, as the dependency rule requires.
- The PH validators live in the domain as value objects. Pydantic schemas call them, so 422 responses carry the right field names.
- A `Clock` port (`now()`) makes expiry and rate windows easy to test.

### D8. Specializations seed
- The migration inserts about 25 PH specializations (codes are slugs such as `internal-medicine`, `obstetrics-gynecology`, `pediatrics`) using `op.bulk_insert`, with fixed UUIDs so the seed is deterministic.
- `GET /api/v1/specializations` lists them sorted by name and is public.
- Admins managing the list is out of scope.

### D9. Frontend
- `api/client.ts` gets `post<T>(path, body)`. The JSON body is already handled by `request`.
- New modules: `api/auth.ts` (signup, confirm, resend) and `api/specializations.ts`.
- Routes:
  - `/signup/doctor` (form)
  - `/signup/check-email` (receives the email through router state, has a resend button)
  - `/verify-email` (confirms on mount with `useMutation`, shows success, expired, or invalid)
  - `/privacy` (placeholder notice showing its version)
- Forms use controlled inputs plus small validators that mirror the backend rules in `src/features/accounts/validation.ts`. No form library is added. Backend 422 `details[].field` and 409 details are mapped onto fields.
- There's a 429 message that shows the `Retry-After` time when present. This needs `ApiError` to expose response headers, or at least `retryAfter`.

### D10. Settings (all documented in `backend/.env.example`)
- `FRONTEND_BASE_URL`
- `MAIL_FROM` and the `SMTP_*` settings
- `EMAIL_VERIFICATION_TTL_HOURS` (default 24)
- `PRIVACY_NOTICE_VERSION` (default `2026-11-draft`)
- `RATE_LIMIT_SIGNUP_PER_IP`, `RATE_LIMIT_SIGNUP_PER_EMAIL`, `RATE_LIMIT_RESEND_PER_IP`, `RATE_LIMIT_RESEND_PER_EMAIL`, `RATE_LIMIT_WINDOW_SECONDS`

Docker Compose sets `FRONTEND_BASE_URL=http://localhost:${FRONTEND_PORT}`.

## Risks / Trade-offs

- [Background email is lost if the process dies between the response and the send] → the user can resend. A durable outbox comes when a worker exists.
- [The `request.client.host` IP is wrong behind a proxy, so all users share one bucket] → configure trusted-proxy handling at deployment, and record it as a follow-up.
- [409 on mobile or PRC reveals that a number is registered] → accepted trade-off (D4). Rate limiting slows down probing.
- [Similar timing is best effort; DB lookups differ slightly between paths] → hashing dominates, and the email is sent after the response. Acceptable for this threat model.
- [The common-password list goes stale or is small] → it's a swappable file. A k-anonymity breach check (HIBP) could be added later behind the same policy function.
- [Fixed windows allow a burst at a window boundary, up to twice the limit] → acceptable for sign-up abuse limits.
- [A doctor never verifies, leaving an orphan account holding a mobile or PRC number] → resend exists. A cleanup policy for unverified accounts (soft-delete after N days) is a follow-up.

## Migration Plan

- One Alembic revision creates `specializations` (with the seed), `users`, `doctor_profiles`, `email_verification_tokens`, and `rate_limit_counters`, plus the triggers on every table except `rate_limit_counters`. The downgrade drops them in reverse.
- The existing coverage tests from US-00.2 will now check real tables. The rate-limit table passes only because it's on the exemption list.
- Rollback: `alembic downgrade -1`. No production data exists yet.

## Open Questions

- Exact wording of the emails and pages, which can be refined in review without changing behavior.
- The full specialization list: the seed starts with the common PH specialties, and adding more is a data change.
