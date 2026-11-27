## Why

Doctors are the supply side of RecliniQ. Until they can create accounts, nothing else in the product (schedules, booking, queues) has anyone to serve. US-01.1 (GitHub issue #7) is the first feature that stores people. It sets up the account model, password hashing, and email verification that patient sign-up (US-01.2) and login (US-01.3) will reuse, so it needs to be built carefully.

**Sequencing:** builds on US-00.2 (soft-delete base model, merged in PR #8). Every new table uses the soft-delete mixin from the start.

## What Changes

- **Doctor sign-up**: a public endpoint and a frontend form collect first name, optional middle name, last name, email, mobile number, password, specialization, PRC license number, and acceptance of the privacy notice. Consent is stored with its timestamp.
- **Philippine domain validation**:
  - Mobile numbers are accepted as `09XXXXXXXXX` or `+639XXXXXXXXX` and stored in E.164 form.
  - PRC license numbers must be numeric, up to 7 digits, and are stored normalized.
  - Specialization is chosen from a `specializations` lookup table, seeded by migration with PH medical specializations and served to the form by a public endpoint.
  - Email, mobile, and PRC license number are each unique among non-deleted accounts. Per the US-00.2 convention, uniqueness uses partial unique indexes (`WHERE deleted_at IS NULL`), so a soft-deleted account doesn't block re-registration.
  - A duplicate mobile number or PRC license number is rejected as a conflict on that field. A duplicate email is handled differently, without revealing it (see Security behaviors).
- **Account states**: kept as two independent fields.
  - Email verification state: unverified, then verified.
  - Professional license state: `pending`, `approved`, or `rejected`. New doctors start as `pending` ("Pending verification").
  - This change only defines and sets these states. Enforcement belongs to later stories: login requires a verified email (US-01.3), publishing schedules requires an approved license (US-02.1), and admin approval of licenses has its own story.
- **Email verification**:
  - Sign-up sends a single-use link containing a random token. Only a hash of the token is stored, and it expires after 24 hours.
  - The user can request a new link. Requesting one invalidates earlier links.
  - The link opens a frontend page, which confirms the token with a `POST`. Link scanners that prefetch `GET` URLs therefore can't use up the token. A valid token marks the email as verified.
- **Security behaviors**:
  - Passwords are hashed with Argon2id. They must be 12–128 characters, with no composition rules, and passwords on a bundled common-password list are rejected.
  - Sign-up does not reveal whether an email is already registered: the response is always "check your email", and the existing owner is notified instead.
  - Sign-up and resend-verification are rate-limited per IP and per email. Over the limit, the response is `429` with `Retry-After`. Counters live in a Postgres table, which login rate limiting (US-01.3) can reuse.
- **Outbound email**: a `Mailer` port with an SMTP adapter. A **Mailpit** service is added to the local Docker Compose stack, so developers can see sent emails in a web inbox.
- **Frontend**: a doctor sign-up page, a "check your inbox" page with a resend option, and an email-verification landing page.

Out of scope: login, logout, and sessions (US-01.3); role enforcement (US-01.4); admin review of PRC licenses (separate story); mobile/SMS verification; uploading a PRC ID image.

## Capabilities

### New Capabilities
- `doctor-registration`: doctor sign-up, including required fields, PH-specific validation, uniqueness, consent capture, password policy, non-enumerating responses, rate limiting, and the initial account and license states.
- `email-verification`: issuing, sending, resending, expiring, and consuming single-use email verification tokens, and marking an account's email as verified. It is shared with patient sign-up (US-01.2).

### Modified Capabilities
- `local-dev-environment`: the one-command local stack also starts a local mail catcher (Mailpit) with a web inbox, and the backend is configured to send email through it.

## Impact

- **Backend**:
  - New `accounts` feature across all layers: domain entities and rules, application services with `UserRepository` / `PasswordHasher` / `Mailer` / token ports, infrastructure adapters, and `/api/v1/auth/...` routes.
  - New settings (SMTP host and port, sender address, frontend base URL for links, token TTL, rate limits), each documented in `.env.example`.
- **Database**: new tables `users`, `doctor_profiles`, `email_verification_tokens`, and a seeded `specializations` lookup, all soft-deletable and protected against hard deletes. Also `rate_limit_counters`, the first entry on the soft-delete exemption list: it holds short-lived counters keyed by hashed IP or email, which must be purged.
- **Dependencies**: `argon2-cffi` for hashing, `aiosmtplib` for sending email, `email-validator` (Pydantic `EmailStr`), and a bundled common-password list.
- **Frontend**: new routes and pages, API functions on the existing `api` client, and form validation that mirrors the backend rules.
- **Infrastructure**: a `mailpit` service in `docker-compose.yml`, and new variables in the root, backend, and frontend `.env.example` files.
- **Follow-ups**: US-01.3 must block login for unverified emails and allow pending doctors to log in. US-02.1 must require an approved license to publish schedules. The admin license-review story needs to be added to the board if it doesn't exist yet.
