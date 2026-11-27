# RecliniQ

Clinic platform for doctor schedules, online consultation booking, live patient queues, and medical records.

## Repository layout

| Path | What |
| --- | --- |
| `backend/` | FastAPI service (Python 3.12, SQLAlchemy 2.x, Alembic, PostgreSQL) using clean architecture |
| `frontend/` | React + TypeScript single-page app built with Vite |
| `docker-compose.yml` | Local stack: PostgreSQL, backend, frontend |
| `openspec/` | Specs and change proposals |

## Prerequisites

- Docker Desktop (for the one-command local stack)
- Optional, for running natively or running checks locally: [uv](https://docs.astral.sh/uv/) and Node.js 24 LTS

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 (the home page shows backend status) |
| Backend API | http://localhost:8000/api/v1/health |
| API docs (Swagger) | http://localhost:8000/api/v1/docs |
| PostgreSQL | `localhost:5432` (user, password, and database `recliniq`) |
| Mailpit (local email inbox) | http://localhost:8025 |

- The backend applies database migrations automatically before it starts serving.
- Backend and frontend reload when you save a file. File polling is on by default because Docker bind mounts on Windows and macOS don't deliver file events. On Linux, set `DEV_WATCH_POLLING=false` in `.env`.
- Database data lives in the `db-data` volume and survives `docker compose down`. Use `docker compose down -v` to wipe it.
- Every email the backend sends locally lands in Mailpit; nothing is delivered externally.
- If a port is taken, change `POSTGRES_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`, or `MAILPIT_UI_PORT` in `.env`.

## Configuration

Every setting is documented in an example file. Real `.env` files are git-ignored, so never commit secrets.

| File | Used by |
| --- | --- |
| `.env.example` → `.env` | Docker Compose (DB credentials, ports, polling) |
| `backend/.env.example` → `backend/.env` | Backend when run natively |
| `frontend/.env.example` → `frontend/.env.local` | Frontend when run natively |

## Running checks locally (same as CI)

```bash
# Backend
cd backend
uv sync
uv run ruff check . && uv run ruff format --check . && uv run mypy
TEST_DATABASE_URL=postgresql+asyncpg://recliniq:recliniq@localhost:5432/recliniq_test uv run pytest

# Frontend
cd frontend
npm ci
npm run lint && npm run typecheck && npm test -- --run && npm run build
```

Integration tests need a **disposable** database because they migrate it up and down. Create one in the running stack with `docker compose exec db createdb -U recliniq recliniq_test`. Without `TEST_DATABASE_URL`, integration tests are skipped.

See `backend/README.md` for the backend architecture and conventions.
