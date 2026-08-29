## Context

See `proposal.md` (Why) and `specs/portal-ui/spec.md`. Today `frontend/src/App.tsx` puts `/` under `Shell`, which calls `GET /auth/me` and sends anonymous users to `/login`. Login then `navigate("/")`. Visual system is a narrow form stack plus RecLinq SVG brand. Booking, schedule, visits, and alerts stay on existing FastAPI routes and PostgreSQL constraints. The SPA must not hold `DATABASE_URL`.

## Goals / Non-Goals

**Goals:**

- Split public vs authenticated React layouts; `/` public, in-app home under `/app`.
- Shared chrome (header, footer, tokens) without a new CSS framework.
- Preserve `?next=` (or equivalent) so Get Care → Sign in → intended screen.
- Leave FastAPI/PostgreSQL booking uniqueness and tenant filters unchanged.

**Non-Goals:**

- New tables, CMS, or public clinic-directory API.
- Live queue transport (SSE/WebSocket); history/queue UI stays request/response as today.
- Component kit (no MUI/Chakra unless a later change requires it).

## Decisions

### 1. Routes (React)

- `/` — public landing (`PublicLayout`).
- `/login`, `/register` — auth pages inside public chrome; after success go to `next` if same-origin path, else `/app`.
- `/app/*` — current `Shell` pages: index home, `book`, `history`, `visits/:id`, `alerts`, `schedule`, `on-behalf`.
- Brand in the header always links to `/`. Header “Home” / “Manage” links to `/app`.

**Alternative:** Keep `/` authenticated and use `/welcome` for marketing — rejected because visitors expect `/` to be the brochure (spec).

### 2. React structure

Colocate portal UI under `frontend/src/portal/` (`PublicLayout`, `LandingPage`, `SiteHeader`, `SiteFooter`, `CareCard`). Keep existing `pages/*` for capability screens. Extend `index.css` with tokens (`--brand`, `--ink`, `--paper`, card/hero/footer). No new npm UI kit.

**Alternative:** Tailwind or a Maxicare-like theme package — rejected; config forbids binding specs to a kit and the SPA is already custom CSS.

### 3. FastAPI / PostgreSQL / contract

- **No schema migrations.** No new routers.
- Authn/authz unchanged: JWT Bearer on existing endpoints; public landing uses no PHI. SPA talks only to HTTP API (`frontend/src/api.ts`).
- Bookings and availability stay conflict-free via existing unique booked-slot constraint and `generate_slots`; portal cards only `navigate` into `BookPage` / `OnBehalfPage`.
- Live queue: **no new channel**. Visit/history lists remain pull-on-load. Adding SSE would be a different change.

**Alternative:** `GET /public/clinic` for hero copy — deferred; static RecLinq copy in the SPA is enough for a single-tenant local compose stack.

### 4. Get Care + staff gates

Public cards: Book → `/login?next=/app/book` (or `/app/book` if already patient). History → `/app/history`. Alerts → `/app/alerts`. Schedule → `/app/schedule` (staff). `Shell` already hides staff nav from patients; staff routes must keep API 403 and a simple in-app refusal if a patient hits `/app/schedule`.

### 5. Visual language (not a clone)

Map Maxicare *patterns* only: sticky header, full-width hero, 2×2 Get Care cards, three “why” points, multi-column footer. RecLinq green `#0b6e4f`, existing `logo-mark.svg` / `favicon.svg`. Do not ship Maxicare assets or orange identity.

### 6. Cursor delivery

Implement via `/opsx-apply` (apply-change) against `tasks.md`. Archive with archive-change after tasks and `openspec validate` succeed. Do not expand into EMR or payments during apply.

## Risks / Trade-offs

- **[Risk] Bookmarks to `/` after login land on marketing, not clinic home.** → Header Manage + post-login `/app`; document in README.
- **[Risk] `next` open redirect.** → Allow only paths starting with `/app`.
- **[Risk] Visual “Maxicare clone” / trademark.** → RecLinq copy and color only; no scraped images.
- **[Trade-off] Static landing copy** vs CMS — static is enough until multi-clinic public sites exist.

## Migration Plan

1. Ship frontend only; `docker compose up --build` for `web`.
2. Rollback: revert SPA routes; API/DB untouched.
3. No additive Alembic work. No destructive DB change.

## Open Questions

None that affect specs or task breakdown. Hero photography can be CSS/gradient placeholders until licensed clinic photos exist.
