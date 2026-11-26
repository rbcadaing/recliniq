## Why

RecliniQ (clinic scheduling, queueing, and medical records) has no code yet. Every story after this one depends on a shared base: soft delete, audit, auth, RBAC, schedules, queueing, and records. User story **US-00.1 Project scaffolding** (Epic 0, P0, status Ready) asks for a FastAPI backend and a React frontend with shared conventions, so the team can build features on a consistent base.

## What Changes

- Add a **FastAPI backend** under `backend/` that follows clean architecture: domain, application, infrastructure, and presentation layers, with dependencies pointing inward.
- Use SQLAlchemy 2.x (async), Alembic migrations, Pydantic v2 schemas, and PostgreSQL. Add typed settings loaded from environment variables.
- Apply backend best practices: a versioned API prefix (`/api/v1`), a consistent error response envelope, structured logging, a request-ID middleware, CORS config, and liveness and readiness health endpoints.
- Add a **React frontend** under `frontend/` built with Vite and TypeScript. It gets client-side routing, a typed API client wrapper with an env-configured base URL, and a home page that shows backend health.
- Add **Docker Compose**, so one command starts PostgreSQL, the backend (which runs migrations on start), and the frontend, all with hot reload.
- Add `.env.example` files that document every config value. `.gitignore` excludes real `.env` files, and no secrets are committed.
- Add **CI with GitHub Actions** that lints, type-checks, and tests both apps on every pull request.
- Add baseline tests: backend pytest (health and readiness against a real Postgres) and frontend Vitest (app render and API client).

## Capabilities

### New Capabilities
- `backend-foundation`: Backend service skeleton: layered architecture, configuration, database/migrations, API versioning, error envelope, health/readiness endpoints, logging and request IDs.
- `frontend-foundation`: Frontend app skeleton: routing, environment-configured API client, error handling, and a health indicator page.
- `local-dev-environment`: One-command local stack (DB, backend, frontend) and documented environment configuration with no committed secrets.
- `continuous-integration`: Automated lint, type-check, and test runs for backend and frontend on every pull request.

### Modified Capabilities
<!-- None: this is the first change in the repository. -->

## Impact

- **New code**: `backend/`, `frontend/`, `docker-compose.yml`, `.github/workflows/ci.yml`, root `README.md`, `.gitignore`, `.env.example` files.
- **Dependencies**: Python 3.12 (FastAPI, SQLAlchemy 2.x, asyncpg, Alembic, Pydantic v2 / pydantic-settings, uvicorn, structlog, pytest, ruff, mypy) managed with `uv`. Node 24 LTS (React 19, Vite, TypeScript, React Router, TanStack Query, Vitest, oxlint, Prettier) managed with `npm`. Node 24 replaces the originally planned Node 20, which reached end of life in April 2026.
- **Infrastructure**: PostgreSQL 16 container for local dev and CI.
- **Repository**: the workspace is not a git repo yet. It must be initialized and connected to GitHub for CI to run.
- **Out of scope** (later stories): soft-delete base model (US-00.2), audit trail (US-00.3), authentication and RBAC (Epic 1), and all domain features.
