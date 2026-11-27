# RecliniQ backend

FastAPI service using clean architecture, async SQLAlchemy 2.x, Alembic, Pydantic v2, and PostgreSQL.

## Architecture

```
app/
  domain/          Entities, value objects, domain errors. Pure Python: no FastAPI or SQLAlchemy imports.
  application/     Use cases/services and the ports (Protocols) they need, e.g. repositories.
  infrastructure/  Adapters implementing ports: SQLAlchemy models, repositories, DB engine/session.
  presentation/    HTTP layer: FastAPI routers, request/response schemas, dependencies, error handlers.
  core/            Cross-cutting setup: settings, logging, middleware.
  main.py          create_app() factory that wires everything together.
```

**Dependency rule:** `presentation → application → domain`. `infrastructure` implements the application ports and is wired in only through `presentation/dependencies.py`. Nothing in `domain` or `application` imports from `infrastructure` or `presentation`.

**Conventions**
- Group code by feature inside each layer (e.g., `application/health/`, `presentation/api/v1/health.py`).
- Keep layers thin. Add an application service only when there is logic beyond pass-through.
- Raise `app.domain.errors.AppError` subclasses for expected failures. They are mapped to the standard error envelope `{"error": {"code", "message", "details", "request_id"}}`.
- All endpoints live under `/api/v1`. OpenAPI is at `/api/v1/openapi.json` and Swagger UI is at `/api/v1/docs`.
- Register new ORM model modules in `app/infrastructure/db/models.py` so Alembic sees them.
- Every setting in `app/core/config.py` must be documented in `.env.example`.

## Running natively

```bash
uv sync
cp .env.example .env          # point DATABASE_URL at a running Postgres
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
```

## Quality checks (same as CI)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest                 # integration tests run when TEST_DATABASE_URL is set
```

## Migrations

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
uv run alembic downgrade -1
```

A test fails if the ORM models contain schema changes that no migration captures.

## Soft delete

Rows are never physically deleted (US-00.2). Deleting a record sets `deleted_at` and `deleted_by` instead.

- **Every model uses `SoftDeleteMixin`** (`app/infrastructure/db/base.py`). `deleted_by` is the acting user's id, or `None` for system actions. It has no foreign key on purpose. A unit test fails if a table lacks the columns, unless it's listed with a reason in `SOFT_DELETE_EXEMPT_TABLES` (`app/infrastructure/db/soft_delete.py`).
- **Deleted rows are hidden by default.** Every ORM `SELECT` gets `deleted_at IS NULL` for soft-deletable models, including joins and relationship loads. To see deleted rows, opt out per statement with `.execution_options(include_deleted=True)`. Raw `text()` queries bypass the filter.
- **Use `SoftDeleteRepository`** (`app/infrastructure/db/repository.py`) as the base for feature repositories: `get(id, include_deleted=False)`, `list_deleted()`, `soft_delete(entity, actor_id)`, and `restore(entity)`. Both `soft_delete` and `restore` are idempotent. `get` uses a `SELECT` rather than `session.get`, so it doesn't return an entity that was soft-deleted earlier in the same session.
- **Hard deletes fail.** `session.delete(entity)` and bulk `delete(Model)` raise `HardDeleteForbiddenError`, which surfaces as a 500 response. A database trigger also rejects raw `DELETE`s.
- **New table migrations must protect the table:**
  ```python
  from app.infrastructure.db.migration_helpers import (
      protect_from_hard_delete,
      unprotect_from_hard_delete,
  )


  def upgrade() -> None:
      op.create_table("things", ...)
      protect_from_hard_delete("things")


  def downgrade() -> None:
      unprotect_from_hard_delete("things")
      op.drop_table("things")
  ```
  An integration test fails if a soft-deletable table has no trigger.
- **Uniqueness:** use `soft_unique_index("uq_things_code_active", "code")` in `__table_args__` instead of `unique=True` or `UniqueConstraint`, so deleted rows don't block new ones. Upserts must repeat the predicate: `ON CONFLICT (code) WHERE deleted_at IS NULL`.
- **No automatic cascade.** Soft-deleting a parent leaves its children untouched. If a feature needs a cascade, its service soft-deletes the children explicitly.
- **Maintenance override** (for operators only; app code never sets it): inside a transaction, run `SET LOCAL recliniq.allow_hard_delete = 'on'` before the `DELETE`.

## Accounts (doctor sign-up and email verification)

The first feature built with ports and adapters; use it as the template.

```
domain/accounts/          values.py (Role, LicenseStatus, parse_email / parse_ph_mobile /
                          parse_prc_license), passwords.py (+ common_passwords.txt), entities.py
application/accounts/     ports.py (Protocols), services.py (SignUpDoctor, ConfirmEmail,
                          ResendVerification), emails.py (templates)
infrastructure/accounts/  models.py (ORM), repositories.py, hasher.py (Argon2id), mailer.py
                          (SmtpMailer, InMemoryMailer), rate_limiter.py (PostgresRateLimiter)
presentation/api/v1/      auth.py, specializations.py; wiring in presentation/dependencies.py
```

- **Domain entities and ORM models are separate.** Repositories map between them, so `domain/` and `application/` never import SQLAlchemy.
- **Services return the emails to send instead of sending them.** Routes deliver them with `BackgroundTasks` after the response, so delivery can't fail or slow the request. Mailer failures are logged with a masked address and never raised.
- **Sign-up never reveals whether an email is registered.** Every non-202 outcome (422, 409 on mobile or PRC, 429) is decided before the email is looked up. A registered email gets the same 202, and its owner gets an email instead.
- **Rate limiting:** `PostgresRateLimiter.hit(bucket, limit=, window_seconds=)` uses fixed windows in `rate_limit_counters`. Buckets are `action:kind:sha256(value)` (from `rate_limit_bucket()`), so no raw IP or email is stored. It commits in its own transaction, so attempts count even when the request fails. The table is the soft-delete exemption, and old windows are purged opportunistically. The client IP is `request.client.host`; trusted-proxy handling is still to do.
- **Error field names:** request validation reports `body.<field>`, while service errors (`FieldConflictError`, unknown specialization) report `<field>`. Clients should match on the last segment.
- **Local email:** everything goes to Mailpit (http://localhost:8025). Tests override `get_mailer` with `InMemoryMailer`, and API integration tests also override `get_session` with the rolled-back test session.

## Sessions (login, refresh, logout, password reset)

- **Access token:** a JWT (HS256, about 15 minutes) signed with `JWT_SECRET`, with claims `sub`, `role`, `iss`, `aud`, `iat`, `exp`, and `jti`. It contains no personal data. `JWT_SECRET` must be 32+ random bytes outside `local`/`test`; startup fails otherwise.
- **Refresh token:** opaque, 30 days, with only its sha256 stored in `refresh_tokens`. Each `/auth/refresh` retires the token and issues a new one in the same `family_id`, keeping the original absolute expiry. Presenting a retired token again counts as **reuse** and revokes the whole family. `/auth/logout` revokes the family. A password reset revokes all of the user's families.
- `RefreshSession` *returns* `RefreshRejected` instead of raising, because raising would roll back the request's unit of work and undo the reuse revocation. The route writes the 401 envelope itself. Keep this pattern for any failure path that must persist writes.
- **Auth dependency:** use `CurrentUserDep` (`app/presentation/security.py`) on protected routes. It decodes the bearer token and **reloads the user**, so deleted accounts are rejected immediately. Failures are `401 not_authenticated` with `WWW-Authenticate: Bearer`. Swagger's **Authorize** button accepts an access token.
- Login runs one Argon2 verify on every path, using a dummy hash for unknown emails. `email_not_verified` (403) is returned only after a correct password. Hashes are upgraded on login when the Argon2 parameters change.
- Password-reset and verification tokens share `_SingleUseTokenRepository`. Superseded tokens are soft-deleted.
