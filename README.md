<img src="frontend/public/logo-mark.svg" alt="RecLinq" height="48">

# RecLinq

Clinic scheduling, booking, visit records, and alerts.

## Local development (Docker Compose)

You do not need Postgres installed on the host.

1. Copy environment defaults:

   ```bash
   cp .env.example .env
   ```

2. Start the stack:

   ```bash
   docker compose up --build
   ```

3. Open the app:

   - Public portal: http://localhost:5173
   - Signed-in clinic workspace: http://localhost:5173/app
   - API health: http://localhost:8000/health
   - OpenAPI: http://localhost:8000/docs

The API container runs `alembic upgrade head` and seeds staff on start.
Use **Get care** on the public portal to sign in and continue directly to
booking, visit history, alerts, or the staff schedule.

### Seed accounts (local)

| Role | Email | Password |
|---|---|---|
| Doctor | doctor@example.com | DoctorPass1! |
| Assistant | assistant@example.com | AssistPass1! |

Patients register from the SPA. Change passwords in `.env` before any real use.

Optional seed after the API is up:

```bash
docker compose exec api python -m app.seed
```

## Tests (API)

From `backend/` with Python 3.12+:

```bash
pip install -r requirements.txt
pytest
```

Or:

```bash
docker compose exec api pytest
```

## Brand assets

| Asset | File | Use |
|---|---|---|
| Logo mark | `frontend/public/logo-mark.svg` | Header, README, marketing |
| App icon | `frontend/public/favicon.svg` | Favicon, apple-touch-icon |

Brand green is `#0b6e4f`. The wordmark is set in the app's system font stack by
`frontend/src/Brand.tsx`, so there is no font file to ship.
