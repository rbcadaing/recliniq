# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

RecliniQ is a clinic platform (doctor schedules, consultation booking, live patient queues, medical records). Monorepo: `backend/` (FastAPI, Python 3.12, async SQLAlchemy 2.x, Alembic, PostgreSQL 16, managed with `uv`) and `frontend/` (React 19 + TypeScript, Vite, TanStack Query, React Router, Node 24).

## Commands

Local stack (applies migrations automatically, hot reload on both services):
```bash
cp .env.example .env && docker compose up --build
docker compose exec db createdb -U recliniq recliniq_test   # one-time: DB for integration tests
```

Backend (run from `backend/`):
```bash
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy   # mypy is strict
uv run pytest                                    # integration tests skipped unless TEST_DATABASE_URL set
TEST_DATABASE_URL=postgresql+asyncpg://recliniq:recliniq@localhost:5432/recliniq_test uv run pytest
uv run pytest tests/unit/test_health.py::test_name   # single test
uv run uvicorn app.main:create_app --factory --reload   # run natively (needs backend/.env)
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

Frontend (run from `frontend/`):
```bash
npm ci
npm run lint          # oxlint --deny-warnings + prettier --check
npm run format        # prettier --write
npm run typecheck
npm test -- --run     # vitest; `npm test` alone runs in watch mode
npx vitest run src/pages/HomePage.test.tsx -t "name"   # single test
npm run build
```

CI (`.github/workflows/ci.yml`) runs exactly the lint/format/typecheck/test/build steps above for both apps, with a Postgres service and `alembic upgrade head` before backend tests.

## Backend architecture

Clean architecture under `backend/app/` (details in `backend/README.md`):
- `domain/` — pure Python, no FastAPI/SQLAlchemy imports. `domain/errors.py` defines `AppError` subclasses (`NotFoundError`, `ConflictError`, `DomainValidationError`, `PermissionDeniedError`, `DependencyUnavailableError`).
- `application/` — services plus the ports (Protocols) they depend on.
- `infrastructure/` — adapters implementing ports (ORM models, repositories, `Database` engine/session wrapper).
- `presentation/` — routers under `api/v1/`, schemas, error handlers, and `dependencies.py`.
- `core/` — settings (pydantic-settings), structlog logging, request-context middleware.

Dependency rule: `presentation → application → domain`. Infrastructure is wired in **only** via `presentation/dependencies.py`, which builds services from `request.app.state` and exposes `Annotated[..., Depends(...)]` aliases (`SettingsDep`, `SessionDep`, etc.). Code is grouped by feature within each layer.

Key conventions:
- `app/main.py:create_app(settings)` is a factory; `Settings` and `Database` live on `app.state`. Tests build their own app by passing settings.
- Raise `AppError` subclasses for expected failures; `presentation/errors.py` maps them (and HTTP/validation/unhandled errors) to the envelope `{"error": {"code", "message", "details", "request_id"}}`. `X-Request-ID` is propagated by middleware and echoed in responses.
- All routes are under `/api/v1` (Swagger at `/api/v1/docs`). Health: `/api/v1/health` and `/api/v1/health/ready` (the latter is the compose healthcheck and checks the DB).
- New ORM model modules must be imported in `app/infrastructure/db/models.py` so Alembic autogenerate sees them. A test fails if models have schema changes not captured by a migration.
- Every setting in `app/core/config.py` must be documented in the corresponding `.env.example`.
- **Soft delete only** (details: `backend/README.md` → Soft delete):
  - Every model uses `SoftDeleteMixin`, and every new table's migration calls `protect_from_hard_delete(table)`. Tests enforce both.
  - Deleted rows are filtered out of all ORM selects by a session-wide listener; use `.execution_options(include_deleted=True)` to see them.
  - `session.delete()` and bulk `delete()` raise `HardDeleteForbiddenError`. Use `SoftDeleteRepository.soft_delete()` / `restore()` instead.
  - Use `soft_unique_index(...)` instead of `unique=True` on soft-deletable tables.
  - `rate_limit_counters` is the one exempt table (`SOFT_DELETE_EXEMPT_TABLES`).
- **Accounts feature is the ports-and-adapters template** (`backend/README.md` → Accounts):
  - Domain dataclasses are separate from ORM models; protocols live in `application/accounts/ports.py`; adapters in `infrastructure/accounts/`; wiring in `presentation/dependencies.py`.
  - Services return emails to send, and routes deliver them via `BackgroundTasks`.
  - Doctor sign-up must not reveal whether an email is registered. Keep every non-202 check *before* the email lookup in `SignUpDoctor`.
- **Auth:** protect endpoints with `CurrentUserDep` from `app/presentation/security.py` (bearer JWT; reloads the user each request). Refresh tokens rotate, and reuse revokes the session. Failure paths that must persist writes (like reuse revocation) return a result instead of raising, because raising rolls back the unit of work. See `backend/README.md` → Sessions.
- Tests: `tests/conftest.py` configures app logging per session, so use `caplog` (not structlog's `capture_logs`) to assert on log events. API integration tests use the `api`/`client`/`signup`/`mailer`/`clock` fixtures from `tests/integration/conftest.py`, which override `get_session` (rolled-back session), `get_mailer` (`InMemoryMailer`), and `get_clock`. Don't mix them with tests that need the real unit of work.

Tests: `tests/conftest.py` gives unit tests an app pointed at an unroutable DB (`127.0.0.1:1`) so accidental DB access fails fast. `tests/integration/` is auto-marked `integration` and skipped without `TEST_DATABASE_URL`; it migrates the DB once per session and wraps each test in a rolled-back transaction (`db_session`, `integration_client` fixtures). Use a disposable DB — migrations run against it. pytest-asyncio is in auto mode with session-scoped loops.

## Frontend architecture

- `src/api/client.ts` is the single entry point for backend calls: `createApiClient(baseUrl)` / `api` adds `X-Request-ID`, and normalizes failures into `ApiError` (`kind: 'http' | 'network'`, `code`, `status`, `requestId`) by parsing the backend error envelope. Per-resource modules (e.g. `api/health.ts`) wrap it and accept an injectable `ApiClient` for testing. Base URL comes from `VITE_API_BASE_URL`.
- Routes are a `RouteObject[]` in `src/routes.tsx` (nested under `Layout`). Server state uses TanStack Query.
- Tests use `renderAt(path, state?)` from `src/test/render.tsx`, which renders the real route tree in a memory router with a non-retrying `QueryClient`, inside `StrictMode`. Stub the backend with `mockApi({'POST /api/v1/...': () => json(...)})` from `src/test/mockApi.ts`.
- **Session (frontend):** `src/auth/session.ts` keeps the access token in memory and the refresh token in `localStorage`. The `api` client adds `Authorization` and, on a 401 from a non-`/auth/` path, calls `refreshSession()` once (single-flight, inside a Web Lock across tabs) and retries. Use `useAuth()` from `src/auth/context.ts` and wrap protected routes in `<RequireAuth>`. Never nest `<ResendVerification>` (a form) inside another form.
- Account forms (`src/features/accounts/`): validators mirror the backend rules, and errors are keyed by backend field name. `fieldErrorsFrom()` maps 422/409 responses onto fields. When passing API functions to `useMutation`, wrap them (`(x) => fn(x)`), because TanStack passes a context second argument.

## Workflow: OpenSpec

Work is spec-driven via OpenSpec (`openspec/`): current capability specs in `openspec/specs/`, active changes in `openspec/changes/`, completed ones in `openspec/changes/archive/`. Use the `opsx:*` / `openspec-*` skills (propose → apply → archive) for feature work. Branches follow `feature/us-<id>-<slug>` with user-story IDs (e.g. US-00.1) referenced in commits; the main branch is `master`.

## Environment notes

The local stack includes Mailpit (web inbox http://localhost:8025); every email the backend sends lands there.

Docker bind mounts on Windows/macOS need file polling (`DEV_WATCH_POLLING=true`, the default); set it to `false` on Linux. Ports are configurable via `POSTGRES_PORT`, `BACKEND_PORT`, `FRONTEND_PORT` in the root `.env`.
