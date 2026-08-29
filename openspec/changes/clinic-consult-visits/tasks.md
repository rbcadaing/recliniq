## 1. Project skeleton

- [x] 1.1 Create `backend/` FastAPI app (health `GET /health`), `.env.example` without secrets, and verify `uvicorn` serves health 200
- [x] 1.2 Create `frontend/` Vite React TypeScript app with React Router and a mobile-first shell (max-width stack layout) and verify `npm run build` succeeds
- [x] 1.3 Add CORS so the SPA origin can call the API and verify a browser or curl OPTIONS/GET health from the documented frontend origin
- [x] 1.4 Add `backend/Dockerfile`, `frontend/Dockerfile`, and `.dockerignore` files; verify each image builds (`docker build`)
- [x] 1.5 Add root Compose file with `db` (Postgres + volume + healthcheck), `api` (depends on healthy db, migrate on start), and `web` (Vite, API URL for local); verify `docker compose up --build` serves health from `api` and the SPA from `web`
- [x] 1.6 Document Compose env (`.env.example`, published ports, seed command) and verify a clean `docker compose up` against that README path

## 2. Database and identity (backend)

- [x] 2.1 Add SQLAlchemy 2.x, Alembic, and PostgreSQL URL from env; create initial migration for `tenants`, `users`, `practitioners` and verify `alembic upgrade head` against Compose `db` (`docker compose exec api alembic upgrade head` or equivalent)
- [x] 2.2 Implement seed: one tenant (timezone), one doctor user+practitioner, one assistant user; verify seed is idempotent and staff can be selected from the DB
- [x] 2.3 Implement `POST /auth/register` (patient only) and `POST /auth/login` (JWT Bearer); verify pytest: register+login succeed, duplicate email 409, patient role cannot be set to staff via register
- [x] 2.4 Implement auth dependency (Bearer → user → tenant) and `GET /auth/me`; verify 401 without token and tenant_id on me matches the user

## 3. Schedule availability (backend)

- [x] 3.1 Alembic migration for `weekly_hours` and `schedule_exceptions`; verify upgrade applies
- [x] 3.2 Implement staff-only CRUD for weekly hours and exceptions (doctor, assistant); verify pytest: patient gets 403, closed date excluded from generated slots
- [x] 3.3 Implement `GET /practitioners/{id}/availability?date=` generating 30-minute slots minus exceptions minus booked; verify listed slots match hours and omit taken `starts_at`

## 4. Consult booking (backend)

- [x] 4.1 Alembic migration for `bookings` including partial unique index on `(practitioner_id, starts_at)` where status is booked, plus cancel columns; verify upgrade applies
- [x] 4.2 Implement patient `POST /bookings` in a transaction (create booking + empty visit record); verify pytest: success consumes slot, second insert same slot returns 409
- [x] 4.3 Implement staff `POST /bookings/on-behalf` (patient_id + slot); verify assistant/doctor succeed, patient caller 403
- [x] 4.4 Implement cancel `POST /bookings/{id}/cancel` with actor, time, optional reason; verify upcoming slot reappears, second cancel 409, past slot not re-offered

## 5. Visit records and files (backend)

- [x] 5.1 Alembic migration for `visit_records` and `visit_documents`; verify upgrade applies
- [x] 5.2 Implement list/get/update visit records with tenant and ownership rules; verify patient sees only own, staff sees tenant patient, other patient 404/403
- [x] 5.3 Implement upload/download (PDF/JPEG/PNG, 10 MiB, disk path per design); verify allowed upload stored, disallowed type/size rejected, download requires auth

## 6. Notifications (backend)

- [x] 6.1 Alembic migration for `in_app_alerts` and `email_outbox`; verify upgrade applies
- [x] 6.2 Emit in-app + outbox rows in the same transaction as book, cancel, record update, and document add; verify pytest row counts and recipient user ids (patient + practitioner)
- [x] 6.3 Implement `GET /alerts`, mark-read, and outbox sender (SMTP or log); verify list is caller-only and mark-read clears unread

## 7. React identity and shell

- [x] 7.1 Typed API client for auth; register/login/logout pages; persist token as designed; verify patient can register and land on a home route
- [x] 7.2 Role-based nav (patient vs doctor vs assistant) usable at phone width; verify staff login shows schedule/booking-on-behalf, patient does not

## 8. React schedule and booking

- [x] 8.1 Staff schedule UI: weekly hours + exceptions; verify saved hours change availability GET
- [x] 8.2 Patient booking UI: pick practitioner, date, remaining slot, confirm; verify slot disappears after book
- [x] 8.3 Staff on-behalf booking UI: pick patient + slot; verify booking appears on that patient’s history
- [x] 8.4 Cancel UI for patient and staff with optional reason and visible cancel actor/time; verify upcoming slot returns to availability

## 9. React visits, files, alerts, mobile

- [x] 9.1 Patient history list + visit detail/update; staff patient-picker + same detail; verify cross-patient access blocked in UI (error state)
- [x] 9.2 Document upload/list/download on visit detail; verify lab/prescription-style files appear for owner and staff
- [x] 9.3 Alerts inbox with 30s poll and mark-read; verify book/cancel/update/upload create alerts for patient and practitioner
- [x] 9.4 Pass a phone-width layout check (register, book, history, cancel, alerts) with no hover-only primary actions; verify by resizing viewport or device emulation

## 10. Integration

- [x] 10.1 README happy path is Docker Compose (`up --build`, migrate/seed if not automatic, URLs); verify a clean clone following README without installing Postgres on the host
- [x] 10.2 End-to-end happy path: staff hours → patient register/book → staff on-behalf book → cancel with log → upload doc → alerts; verify against specs scenarios or an e2e/API script
