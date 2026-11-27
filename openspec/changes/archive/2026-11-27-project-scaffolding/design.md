## Context

Greenfield repository: the only content is OpenSpec tooling, and the folder is not yet a git repository. For motivation see proposal.md (Why); requirements are in `specs/`. The product is a Philippine clinic platform handling medical data (Data Privacy Act), so later stories need soft delete (US-00.2), auditing (US-00.3), and RBAC (US-01.4). This scaffold must make those easy to add without restructuring.

## Goals / Non-Goals

**Goals:**
- A backend layout where business rules have no dependency on FastAPI or SQLAlchemy, so features can be unit-tested and the persistence layer can be swapped or extended (e.g., the soft-delete repository filter in US-00.2).
- One obvious place for each cross-cutting concern: config, DB session, errors, logging, request ID.
- Fast feedback: the local stack starts with one command, and CI finishes in a few minutes.

**Non-Goals:**
- No domain entities, auth, or business endpoints. The only endpoints are health checks.
- No production deployment, container registry, or infra-as-code.
- No UI design system or component library choice yet. Plain CSS is fine for the health page.

## Decisions

### Repository layout: monorepo with `backend/` and `frontend/`
```
backend/
  app/
    domain/          # entities, value objects, domain errors (pure Python)
    application/     # use cases / services, repository interfaces (ports)
    infrastructure/  # SQLAlchemy models, repositories, db session, settings
    presentation/    # FastAPI routers, Pydantic schemas, dependencies, error handlers
    core/            # config, logging, middleware (request ID)
    main.py          # app factory: create_app()
  alembic/
  tests/ (unit/, integration/)
  pyproject.toml
frontend/
  src/ (api/, routes/, pages/, components/, main.tsx)
docker-compose.yml
.github/workflows/ci.yml
```
- **Rationale:** one PR can change API and UI together, and a single CI workflow covers both. *Alternative:* separate repos. Rejected because it adds coordination overhead for a small team.
- Dependency rule: `presentation → application → domain`. `infrastructure` implements the application ports. `domain` imports nothing from frameworks. Within each layer, code is organized by feature package (e.g., `application/health/`) so later epics add folders instead of growing shared files.

### Backend stack
- **Python 3.12, FastAPI, SQLAlchemy 2.x async + asyncpg, Alembic, Pydantic v2 + pydantic-settings, uvicorn.** The story requires these. Async fits the I/O-bound workload and the live queue (Epic 4).
- **`uv` for dependency management** (`pyproject.toml` + `uv.lock`). *Alternatives:* Poetry, pip-tools. `uv` is the fastest, gives reproducible locks, and is well supported in CI.
- **Ruff** for lint and format, **mypy (strict on `app/`)** for types, **pytest + pytest-asyncio + httpx AsyncClient** for tests.
- **structlog** for structured logs: JSON when `APP_ENV != local`, console otherwise. Request ID is bound through contextvars.
- **App factory (`create_app(settings)`)** so tests can build an app with overridden settings. The DB session is provided through a FastAPI dependency that yields an `AsyncSession` with a unit-of-work commit/rollback.
- **Declarative base** with a naming convention for constraints, so Alembic autogenerate gives stable names. A shared `TimestampMixin` (`created_at`, `updated_at`) is included now. Soft-delete columns are left to US-00.2.
- **Alembic async env** reads the DB URL from settings, never from `alembic.ini`. An initial empty baseline revision is added. A test runs `alembic check` (or compares the metadata diff) to enforce the "schema drift" scenario.
- **Error handling:** a domain `AppError` hierarchy (`NotFoundError`, `ConflictError`, `ValidationError`, ...) is mapped by exception handlers to the envelope `{"error": {"code", "message", "details", "request_id"}}`. Starlette `HTTPException` and `RequestValidationError` are handled too.

### Frontend stack
- **Vite + React 19 + TypeScript 7 (strict)**, **React Router v8**, **npm** (lockfile committed). *Updated during implementation:* current releases were used instead of React 18 and Router v6, because the Vite template now ships them.
- **API client:** a thin `fetch` wrapper (`src/api/client.ts`) that reads `import.meta.env.VITE_API_BASE_URL`, sets `X-Request-ID`, parses the error envelope into an `ApiError` class, and maps network failures to `ApiError{kind: "network"}`. *Alternative:* axios. Not needed, because fetch keeps the bundle small. **TanStack Query** handles server state (caching, loading/error states), since nearly every later screen needs it.
- **oxlint (react, react-hooks, typescript, import, jsx-a11y, vitest rules) + Prettier**, **Vitest + React Testing Library**, with `fetch` mocked in API client tests. *Updated during implementation:* typescript-eslint supports only TypeScript <6.1, and the Vite template uses TypeScript 7 with oxlint, so oxlint replaced ESLint.

### Local environment
- **Docker Compose services:** `db` (postgres:16-alpine, named volume, `pg_isready` healthcheck), `backend` (Python image, source bind-mounted, command `alembic upgrade head && uvicorn --reload`, `depends_on: db: service_healthy`), and `frontend` (node:24 image, source bind-mounted, Vite dev server on 0.0.0.0). Ports: 5432, 8000, 5173. File-watch polling (`DEV_WATCH_POLLING`) is **on by default**: testing on Windows showed bind-mount file events never reached the containers, so reload did not work without polling.
- **Env files:** root `.env.example` for compose and DB credentials, `backend/.env.example`, `frontend/.env.example`. `.gitignore` covers `.env`, `.env.*` and keeps `!.env.example`.
- The start command is `docker compose up --build`, documented in `README.md`.

### CI
- **GitHub Actions** (`.github/workflows/ci.yml`), triggered on `pull_request` and on `push` to `main`. There are two parallel jobs:
  - `backend`: setup uv, `uv sync --frozen`, `ruff check`, `ruff format --check`, `mypy`, `alembic upgrade head`, `pytest`, with a `postgres:16` service container.
  - `frontend`: setup node 24 with npm cache, `npm ci`, `npm run lint`, `npm run typecheck`, `npm test -- --run`, `npm run build`.
- **Rationale:** the project board is on GitHub, so Actions needs no extra service.

## Risks / Trade-offs

- [Clean architecture adds boilerplate for simple CRUD] → Keep the layers thin. Add a use case only when there is logic beyond pass-through, and document the convention in `backend/README.md`.
- [Bind mounts on Windows can make hot reload slow or unreliable] → Enable polling (`WATCHFILES_FORCE_POLLING`, Vite `server.watch.usePolling`) behind an env flag, and document running the apps natively as an alternative.
- [The repo isn't on GitHub yet, so CI can't be verified] → The tasks include `git init`, and a final step pushes a branch and opens a PR to watch CI go green.
- [Async SQLAlchemy test isolation] → Each test runs inside a transaction that is rolled back, using one test database migrated once per session.

## Migration Plan

Not applicable: nothing exists yet. Rollback means reverting the commit.

## Open Questions

- Which GitHub repository will host the code? The project board belongs to `rbcadaing`, but no repo is linked. This doesn't affect the scaffold contents.
- Will production hosting (e.g., Fly, Render, AWS) shape container images later? The dev Dockerfiles are kept simple, and production images are deferred.
