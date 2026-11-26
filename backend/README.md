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
