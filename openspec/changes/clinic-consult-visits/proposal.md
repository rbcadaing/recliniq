## Why

Clinics still coordinate visits through notebooks, chat, and memory. Patients cannot see real availability, staff re-type bookings, records live in folders, and cancellations leave no trail. RecLinq needs a first product slice: practitioners publish when they can see patients, people book (or staff book for them), visits and files stay with the clinic tenant, and everyone who should know gets an alert.

## What Changes

- Practitioners publish recurring clinic hours, blocks, and bookable consultation slots (or remaining capacity) per clinic tenant.
- Patients register, log in, and book a consultation against a practitioner’s remaining availability.
- A doctor or clinic assistant can create a booking for a patient (walk-up or phone) without that patient using self-service.
- Patients see their own consultation visit history for that clinic.
- Doctor, patient, and assistant can view and update visit records and upload supporting files (lab results, prescriptions, and similar).
- Patient, doctor, or assistant can cancel a booking; the system records who cancelled, when, and an optional reason.
- Alerts fire for booking created, updated, cancelled, and visit-record/document changes to the people who need to know.
- React UI is usable on a phone (responsive layout, not a separate native app).
- Local development runs in containers via Docker Compose (PostgreSQL, API, SPA).

## Non-goals

- Full EMR, billing, insurance, pharmacy, or teleconsult.
- Waiting-room live queue / “now serving” (follow-up change).
- SMS/WhatsApp (email + in-app alerts for this change).
- Public clinic marketplace; one clinic tenant seeded for the first deployment.
- Patient-to-patient visibility of other people’s visits or files.

## Capabilities

### New Capabilities

- `identity`: Patient self-registration and login; doctor and assistant staff login; role-based access inside a clinic tenant.
- `schedule-availability`: Practitioner (or assistant) plots clinic hours, exceptions, and bookable consultation capacity.
- `consult-booking`: Patient and staff booking against availability; staff booking on behalf of a patient; cancellation with an actor audit log.
- `visit-records`: Per-patient consultation history; visit notes; supporting document upload/view for allowed roles.
- `notifications`: In-app and email alerts for booking and record updates.

### Modified Capabilities

- (none — greenfield)

## Impact

Greenfield RecLinq app: React (TypeScript) SPA, FastAPI API, PostgreSQL (Alembic), orchestrated locally with Docker Compose. New tenant-scoped tables for users, roles, schedules, bookings, visit records, files, audit events, and notification outbox. All patient and schedule data isolated per clinic tenant. No existing APIs to break.
