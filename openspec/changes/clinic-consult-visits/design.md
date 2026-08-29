## Context

Greenfield RecLinq repo (OpenSpec only; no application code). Constraints: React (TypeScript) SPA, FastAPI, PostgreSQL via Alembic and SQLAlchemy 2.x. Motivation: `proposal.md`. Behavior: delta specs under `specs/`. Live waiting-room queue is out of product scope for this change; “queue consistency” here means **bookable capacity vs bookings**, not a floor display.

## Goals / Non-Goals

**Goals:**

- One clinic tenant, multiple practitioners, roles patient / doctor / assistant.
- Availability derived from weekly hours minus exceptions minus active bookings; bookings take a unit in a transaction that cannot double-book.
- SPA never holds `DATABASE_URL`; files and auth secrets stay server-side / env.
- Delivery: implement with `/opsx-apply` against `tasks.md`; archive later with `/opsx-archive`.
- Local stack is `docker compose up` (Postgres, API, SPA); secrets only via env files not committed with passwords.

**Non-Goals:**

- Native apps, SMS, S3-only storage, SSO, multi-tenant marketplace UI.
- SSE/WebSocket live queue board.
- Schema teardown/rollback of production data (first deploy is additive from empty).
- Kubernetes / cloud production deploy (Compose is for local development).

## Decisions

### 1. Repo layout and API contract

**Choice:** `frontend/` Vite + React Router; `backend/` FastAPI. OpenAPI from FastAPI is the contract; frontend uses a typed client generated or hand-written from that schema.

**Why:** Matches stack rules; two deployables, one tenant.

**Alternative:** Next.js or Django — rejected (stack is SPA + FastAPI).

### 1b. Local containers (Docker Compose)

**Choice:** Root `compose.yaml` (or `docker-compose.yml`) with three services: `db` (official Postgres image, named volume, healthcheck), `api` (build `backend/`, wait for healthy `db`, run Alembic then uvicorn, bind-mount source for live reload), `web` (build `frontend/`, Vite dev server, `VITE_API_URL` pointing at the `api` service as the browser-reachable host/port documented in README). Shared Docker network. Upload files on a named volume mounted into `api`. Env from `.env` / `.env.example` (no real passwords in git). `.dockerignore` on backend and frontend.

**Why:** One command for Postgres + API + SPA; matches “containers for local development.” Tests can still run in the `api` image (`docker compose exec api pytest`) against Compose Postgres.

**Alternative:** Compose only for `db`, run API/SPA on the host — rejected as the requested default; host-run remains possible but undocumented as the happy path.

**Production:** Compose is not the production orchestrator.

### 2. Authn / authz

**Choice:** Email + password (bcrypt). JWT access token (short-lived) in `Authorization: Bearer` after login; staff and patients share one login endpoint, role comes from `users.role`. Patient `POST /auth/register`. Staff rows created by bootstrap/seed, not public register. Every route: resolve user → `tenant_id` from user → filter queries by tenant. Forbidden if role not in the allow-list for that operation.

| Surface | Patient | Doctor | Assistant |
|---|---|---|---|
| Plot hours / exceptions | no | yes (self or any practitioner in tenant) | yes (any practitioner in tenant) |
| Self-book | yes | no (use on-behalf) | no |
| Book on behalf | no | yes | yes |
| Cancel own / any in tenant | own | any | any |
| Visit list/update/docs | own | any in tenant | any in tenant |

SPA stores the access token in memory (plus `sessionStorage` only if needed for refresh UX); no DB URL in the client.

**Alternative:** httpOnly session cookies — better CSRF story with SameSite; can switch later without spec change. JWT is simpler for a first API client.

### 3. Availability model (slots)

**Choice:** Tenant timezone on `tenants`. Practitioner `weekly_hours` (weekday + start/end). `schedule_exceptions` (closed date or blocked interval). Bookable units are **fixed 30-minute slots** generated in the service layer from hours minus exceptions. `bookings` rows hold `starts_at` (timestamptz). Partial unique index: unique `(practitioner_id, starts_at)` WHERE `status = 'booked'`. Insert booking inside a transaction; unique violation → 409 not available.

**Why:** Conflict-free capacity is a DB constraint, not a check-then-insert race. 30 minutes is a recorded default (change later without rewriting the unique-key idea).

**Alternative:** Session capacity counters — better for walk-in waves; weaker “pick a time” UX. Slots match self-service booking.

### 4. Booking and visit record lifecycle

**Choice:** Creating a booking also creates an empty `visit_records` row (1:1 `booking_id`). Cancel sets `status = cancelled`, `cancelled_by_user_id`, `cancelled_at`, `cancel_reason`; does not delete history. Past `starts_at` is not reopened for booking.

**Why:** History and documents need a stable visit even if notes are empty.

### 5. Files

**Choice:** Store blobs on local disk (or volume) under `{tenant_id}/{visit_id}/{uuid}` with metadata in `visit_documents` (filename, content_type, size, uploaded_by). Allow PDF, JPEG, PNG; max 10 MiB. Download via authenticated GET, not public URLs.

**Why:** No object-store dependency for v1.

**Alternative:** S3 — defer until ops needs it.

### 6. Notifications

**Choice:** On domain events (booked, rescheduled if implemented, cancelled, record updated, document added), insert `in_app_alerts` and `email_outbox` in the same transaction as the domain write. A background poller (FastAPI lifespan task or `POST /internal/run-outbox` in dev) sends email via SMTP; if SMTP unset, log the message (dev). React **polls** `GET /alerts` every 30s while the app is open — not WebSocket. Live queue board is not built.

**Why:** Outbox keeps email consistent with the write; polling is enough for alerts without a push stack.

**Alternative:** SSE for alerts — extra infra; not required by specs.

### 7. FastAPI and React module shape

**Backend:** routers `auth`, `schedule`, `bookings`, `visits`, `alerts`; services for availability generation, booking transaction, files, notify; repositories wrapping SQLAlchemy.

**Frontend:** feature folders `auth`, `schedule`, `bookings`, `visits`, `alerts`; mobile-first layout (stack, full-width actions, no hover-only cancel).

### 8. PostgreSQL (additive)

Tables: `tenants`, `users`, `practitioners`, `weekly_hours`, `schedule_exceptions`, `bookings`, `visit_records`, `visit_documents`, `in_app_alerts`, `email_outbox`. First migration creates all; no destructive steps.

## Risks / Trade-offs

- [Clock / DST] → Store timestamptz; generate slots in tenant TZ with a well-known library; document tenant TZ as immutable after seed unless a later change says otherwise.
- [Email never sent] → Outbox retries; UI still has in-app alerts.
- [Staff password bootstrap] → Seed one doctor and one assistant in `.env.example` for local; rotate in real deploy.
- [Patient updates clinical notes] → Specs allow it; doctors can overwrite. No legal-hold/versioning in v1 (trade-off vs full EMR).
- [30-min slots too rigid] → Duration is a constant in the availability service; unique key stays on `starts_at`.

## Migration Plan

Empty database: `docker compose up --build`, API container runs Alembic then seed (or a documented `compose exec` seed), SPA talks to published API port. Rollback local: `docker compose down -v` wipes the Postgres volume. Production later: additive Alembic only; not Compose teardown.

## Open Questions

- Exact SMTP provider in production (env-shaped so it does not change tasks).
- Whether assistants may plot hours for every practitioner (assumed yes).
