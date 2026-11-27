## Why

RecliniQ stores medical data that must never be lost and must stay auditable (Data Privacy Act, RA 10173). US-00.2 (GitHub issue #6) makes soft deletion the only way to remove data. No tables exist yet, and US-01.1 (doctor sign-up) is about to add the first ones (`users`, `doctor_profiles`), so this foundation has to land first.

## What Changes

- **Soft-delete mixin** for ORM models:
  - `deleted_at` is a nullable `timestamptz`.
  - `deleted_by` is a nullable UUID holding the actor's id. It deliberately has **no foreign key**, so the mixin works on any table (including `users` itself), allows system actors, and matches the "who did it" pattern of the upcoming audit trail (US-00.3).
  - An `is_deleted` helper.
- **Deleted rows are excluded by default**:
  - A global SQLAlchemy hook (`do_orm_execute` + `with_loader_criteria`) adds `deleted_at IS NULL` to every ORM select, including relationship loads and joins, for models that use the mixin.
  - Callers opt out explicitly with an `include_deleted` execution option.
- **Hard deletes are blocked at two layers**:
  - **Runtime**: an ORM guard raises an error when a soft-deletable entity is deleted through the session or a bulk `DELETE` statement.
  - **Database**: a `BEFORE DELETE` trigger on every soft-deletable table raises an error, so raw SQL is caught too. Migrations provide a reusable helper that attaches the trigger to new tables.
  - An automated test fails if any code path issues a hard delete.
- **Repository API**: `soft_delete(entity, actor_id)` sets `deleted_at` / `deleted_by`, and `restore(entity)` clears them. Queries can include deleted rows explicitly when listing them for restore.
- **Conventions**, documented in `backend/README.md` and `CLAUDE.md`:
  - Unique constraints on soft-deletable tables use **partial unique indexes** (`WHERE deleted_at IS NULL`), so a deleted row doesn't block re-creation.
  - Soft deletion does **not** cascade automatically. Each feature decides explicitly in its service layer whether children are deleted with the parent.

Out of scope, moved to other stories:
- The HTTP endpoints for Admin and Clinic Staff to list and restore deleted records, and their permissions, belong to US-06.3 (Restore soft-deleted data) and US-01.4 (Role-based access control). This change provides the mechanism they will use.
- Static lint checks for `DELETE` in CI belong to US-00.4.

## Capabilities

### New Capabilities
- `soft-delete`: soft-delete columns, default exclusion of deleted rows with explicit opt-out, the soft-delete and restore operations, the runtime and database guards against hard deletes, and the partial-unique and no-auto-cascade conventions.

### Modified Capabilities
<!-- None: the existing backend-foundation migration requirement is unchanged; this adds a new capability on top. -->

## Impact

- **Backend**:
  - New code in `app/infrastructure/db/`: the mixin, the session event hooks, and a delete guard registered on the `Database` session factory.
  - A soft-delete repository base in infrastructure.
  - An infrastructure error for forbidden hard deletes. It is a programming defect, so it surfaces as a 500 response rather than a user-facing `AppError`.
- **Migrations**: a reusable Alembic helper (or a shared PL/pgSQL function created in a migration) for the `BEFORE DELETE` trigger. Every future soft-deletable table must apply it, and a test verifies that.
- **Tests**:
  - Unit tests for the query filter and the guard, using test-only models.
  - Integration tests that prove the trigger blocks raw `DELETE` and that partial unique indexes allow re-creation after a soft delete.
- **Downstream**: US-01.1 doctor sign-up (`users`, `doctor_profiles`, verification tokens) builds directly on this. US-00.3 audit trail and US-06.3 restore endpoints reuse the repository API.
- **No new runtime dependencies.**
