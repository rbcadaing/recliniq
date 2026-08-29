## Why

RecLinq’s SPA is a functional form stack. Patients and staff need a public healthcare-portal look—hero, “get care” actions, sticky header with RecLinq branding, and a footer—modeled on sites like [Maxicare](https://www.maxicare.com.ph/) so the product feels like a clinic, not an admin tool.

## What Changes

- Add a **public landing** (no login required) with RecLinq logo, hero, Get Care cards (book, history/queue, alerts, staff schedule), a short “why RecLinq” strip, and footer quick links.
- Restyle the **React chrome** (header, nav, auth pages, authenticated home) to the same visual language: RecLinq green `#0b6e4f`, wordmark, card grids, large primary CTAs.
- Keep **existing routes and roles**: patient book/history/records; doctor/assistant schedule and on-behalf booking. Landing CTAs deep-link into those surfaces (sign-in first when required).
- **BREAKING (UX only):** `/` is a public marketing home instead of the authenticated shell. Logged-in users still reach an in-app home (e.g. `/app` or role dashboard) from header “Manage” / “Home”.

## Non-goals

- No Maxicare trademarks, copy, products, raffles, SME plan builder, or visual clone of their orange brand.
- No HMO membership, eShop, payments, teleconsult, homecare, live chat, newsletter, or provider/agent recruitment.
- No EMR, no new PostgreSQL tables, no change to booking conflict rules or tenant isolation.

## Capabilities

### New Capabilities

- `portal-ui`: Public RecLinq landing and shared healthcare-portal chrome (header, footer, Get Care cards, auth and in-app shells) for patient, doctor, and assistant on desktop and phone-width viewports.

### Modified Capabilities

- (none — main `openspec/specs/` is empty until `clinic-consult-visits` is archived; booking/identity behavior stays as implemented except public `/`.)

## Impact

- **React (TypeScript) SPA:** layout, CSS, routes, `Brand`, login/register, home. Vite public assets stay RecLinq SVGs.
- **FastAPI + PostgreSQL:** no API or schema change unless a tiny public clinic-name endpoint is added; default is static tenant copy in the SPA.
- **Docker Compose:** unchanged; verify `web` at 5173.
- Delivery: Cursor OpenSpec apply-change against `tasks.md`.
- Detail: `design.md`.
