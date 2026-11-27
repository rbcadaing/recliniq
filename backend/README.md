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
