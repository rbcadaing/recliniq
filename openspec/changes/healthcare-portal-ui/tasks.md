## 1. Backend (FastAPI / PostgreSQL)

- [x] 1.1 Confirm no Alembic revision is required for this change (no new tables). Verify `openspec/changes/healthcare-portal-ui/design.md` still says no schema work and `backend/alembic/versions/` is unchanged.
- [x] 1.2 Re-run API tests so booking uniqueness and auth gates still hold: from `backend/` run `pytest` (or `docker compose exec api pytest`) and confirm the suite passes, including conflict/on-behalf coverage.

## 2. Frontend — tokens and chrome

- [x] 2.1 Add CSS tokens (`--brand` `#0b6e4f`, ink, paper) plus hero, card, sticky header, and footer rules in `frontend/src/index.css`. Verify `npm run build` in `frontend/` succeeds.
- [x] 2.2 Add `frontend/src/portal/SiteHeader.tsx` and `SiteFooter.tsx` using RecLinq `Brand` and existing SVGs only (no third-party marks). Verify header shows Register/Sign in when logged out and Log out + Manage (`/app`) when logged in (manual or component render).
- [x] 2.3 Add `frontend/src/portal/PublicLayout.tsx` wrapping outlet with header/footer. Verify login and register still type-check via `npm run build`.

## 3. Frontend — routes and landing

- [x] 3.1 Move authenticated routes under `/app` in `frontend/src/App.tsx`; make `/` render the public landing. Verify unauthenticated `/` no longer redirects to login (browser or React Router smoke).
- [x] 3.2 Implement `frontend/src/portal/LandingPage.tsx` with hero, Get Care cards (Book, History, Alerts, Schedule), why-RecLinq strip, and footer links. Verify phone-width layout (no desktop-only control) with a ~390px screenshot or viewport check.
- [x] 3.3 Wire Get Care / footer links: Book → `/login?next=/app/book` (or `/app/book` if patient session); History/Alerts/Schedule similarly. Verify `next` accepts only paths that start with `/app`.

## 4. Frontend — auth and in-app home

- [x] 4.1 Update `LoginPage` and `RegisterPage` to sit in public chrome and, on success, navigate to a safe `next` or `/app`. Verify staff and patient login still call existing `POST /auth/login` and `POST /auth/register` (no new FastAPI routes).
- [x] 4.2 Restyle `Shell` nav to portal cards/links; point brand to `/` and in-app home to `/app`. Verify patients do not see Schedule / Book for patient; doctors/assistants do.
- [x] 4.3 Restyle authenticated `HomePage` as role-specific Get Care cards. Verify patient home omits staff actions; doctor home includes schedule and book-for-patient.
- [x] 4.4 If a patient opens `/app/schedule` or `/app/on-behalf`, show an in-app refusal (API 403 remains). Verify they cannot plot another tenant’s hours.

## 5. Integration

- [x] 5.1 Update README: public `/`, in-app `/app`, seed accounts unchanged. Verify a reader can follow Compose steps without hitting a dead `/` login loop.
- [x] 5.2 With Compose (`docker compose up --build`), verify visitor sees landing at http://localhost:5173, patient can register/sign in and book a slot via Get Care → Book (existing conflict-free API), and a doctor can open Schedule from `/app`. Confirm http://localhost:8000/health still works.
