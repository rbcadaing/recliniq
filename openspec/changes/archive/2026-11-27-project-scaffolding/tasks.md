## 1. Repository setup

- [x] 1.1 Run `git init`, add root `.gitignore` (Python, Node, `.env`, `.env.*`, `!.env.example`, IDE files), and verify `git check-ignore .env` reports it ignored
- [x] 1.2 Create root `README.md` with project overview, prerequisites (Docker, uv, Node 20), and quick-start placeholder; verify it renders

## 2. Backend skeleton

- [x] 2.1 Initialize `backend/` with `uv init`, `pyproject.toml` (Python 3.12), and add FastAPI, uvicorn, SQLAlchemy 2.x, asyncpg, Alembic, pydantic-settings, structlog plus dev deps (pytest, pytest-asyncio, httpx, ruff, mypy); verify `uv sync` succeeds and `uv.lock` is created
- [x] 2.2 Create clean-architecture package layout (`app/domain`, `app/application`, `app/infrastructure`, `app/presentation`, `app/core`) with a short `backend/README.md` describing the dependency rule; verify `python -c "import app"` works
- [x] 2.3 Configure ruff (lint + format) and mypy strict in `pyproject.toml`; verify `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy app` pass
- [x] 2.4 Implement `core/config.py` settings (APP_NAME, APP_ENV, APP_VERSION, DATABASE_URL, CORS_ORIGINS, LOG_LEVEL) with validation; verify a unit test shows startup fails naming a missing DATABASE_URL without echoing secrets
- [x] 2.5 Implement structlog logging setup (JSON outside `local`) and request-ID middleware honoring/generating `X-Request-ID` plus per-request access log; verify tests for supplied and generated request IDs pass
- [x] 2.6 Implement domain `AppError` hierarchy and exception handlers producing the standard error envelope for AppError, HTTPException, RequestValidationError, and unhandled exceptions; verify tests for 404, 422 (with field details), and 500 (no stack trace) pass
- [x] 2.7 Implement `create_app(settings)` factory with `/api/v1` router, CORS from settings, and OpenAPI enabled; verify tests for allowed vs disallowed origin and OpenAPI document pass

## 3. Database and migrations

- [x] 3.1 Implement async engine/session factory and `get_session` dependency (unit-of-work commit/rollback) in `infrastructure/db`, plus declarative `Base` with constraint naming convention and `TimestampMixin`; verify `mypy` passes
- [x] 3.2 Initialize Alembic with async `env.py` reading DATABASE_URL from settings and `target_metadata = Base.metadata`; create empty baseline revision; verify `alembic upgrade head` and `alembic downgrade base` succeed against local Postgres
- [x] 3.3 Add pytest fixtures: session-scoped migrated test DB and per-test transactional rollback session; add schema-drift test (`alembic check` / metadata compare); verify the drift test passes now and fails when a model is added without a migration

## 4. Health endpoints

- [x] 4.1 Implement `GET /api/v1/health` (status, app name, version) via presentation router + application service; verify test asserts 200 and body shape
- [x] 4.2 Implement `GET /api/v1/health/ready` running a DB check through an application port implemented in infrastructure; verify tests for 200 when DB up and 503 envelope (no credentials leaked) when DB check fails

## 5. Frontend skeleton

- [x] 5.1 Scaffold `frontend/` with Vite React-TS template (strict TS), add React Router, TanStack Query, ESLint (typescript-eslint, react-hooks), Prettier, Vitest + React Testing Library; add `lint`, `typecheck`, `test`, `build` npm scripts; verify each script runs successfully
- [x] 5.2 Implement `src/api/client.ts` fetch wrapper using `VITE_API_BASE_URL`, sending `X-Request-ID`, and `ApiError` normalizing envelope errors and network failures; verify Vitest tests cover success, envelope error, and network failure
- [x] 5.3 Add router with Home and NotFound routes; verify tests render Home at `/` and NotFound (with link home) at an unknown path
- [x] 5.4 Implement Home page backend status indicator using TanStack Query against `/api/v1/health`; verify tests show "online + version" on success and "offline" on failure without crashing

## 6. Local environment

- [x] 6.1 Add `backend/Dockerfile` (dev) and `frontend/Dockerfile` (dev); verify `docker build` succeeds for both
- [x] 6.2 Add `docker-compose.yml` with `db` (postgres:16-alpine, named volume, pg_isready healthcheck), `backend` (bind mount, `alembic upgrade head && uvicorn --reload`, depends_on healthy db), `frontend` (bind mount, Vite dev server on 0.0.0.0), and optional polling env for Windows; verify `docker compose config` is valid
- [x] 6.3 Add `.env.example` (root), `backend/.env.example`, `frontend/.env.example` documenting every config value with descriptions and safe defaults; verify every setting read in `config.py` and every `VITE_*` var used appears in an example file
- [ ] 6.4 End-to-end check: from a clean state run `docker compose up --build`; verify migrations apply, `curl localhost:8000/api/v1/health/ready` returns 200, the frontend at `localhost:5173` shows backend online, editing a backend file triggers reload, and data persists across `docker compose down`/`up`
- [x] 6.5 Complete root `README.md` quick-start (copy env files, start command, URLs, running tests/lint natively); verify steps match the e2e check

## 7. Continuous integration

- [x] 7.1 Add `.github/workflows/ci.yml` triggered on `pull_request` and push to `main` with a `backend` job (uv sync --frozen, ruff check, ruff format --check, mypy, alembic upgrade head, pytest with postgres:16 service) and a `frontend` job (npm ci, lint, typecheck, test, build); verify the YAML is valid (e.g., `actionlint` or GitHub workflow parse)
- [x] 7.2 Run the full backend and frontend check commands locally exactly as CI does; verify all pass
- [x] 7.3 Connect the repo to GitHub, push a branch, and open a PR; verify both CI jobs run and pass (deferred until the user confirms the target repository)
