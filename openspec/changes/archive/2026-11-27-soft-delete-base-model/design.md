## Context

See proposal.md (Why) for motivation and specs/soft-delete/spec.md for the required behavior.

Current state, from US-00.1:
- `app/infrastructure/db/base.py` defines `Base`, which has a naming convention, and `TimestampMixin`.
- `Database` wraps an async engine and an `async_sessionmaker`.
- Integration tests create their own `AsyncSession` bound to a connection that is rolled back at the end.
- Alembic autogenerates from `Base.metadata`, and the only migration is an empty baseline.
- No application tables exist yet, so this change has to be proven with test-only models and tables.

## Goals / Non-Goals

**Goals:**
- Safe defaults: a developer who writes an ordinary query gets correct behavior without remembering to add a filter.
- Protection at both the ORM and the database layer, each checked by tests, so a missing protection can't go unnoticed.
- Keep it simple for feature stories: adding one mixin and one migration helper call should be enough.

**Non-Goals:**
- HTTP endpoints and role checks for listing or restoring deleted records (US-06.3, US-01.4).
- Audit log entries for delete and restore (US-00.3). The repository methods are the hook points where it will plug in later.
- Physically purging data, for example erasure requests under the Data Privacy Act. The maintenance override only makes this possible later; no workflow is built now.

## Decisions

### D1. `SoftDeleteMixin` with `deleted_by` as a plain UUID (no FK)
The mixin lives in `infrastructure/db/base.py` next to `TimestampMixin` and adds:
- `deleted_at: Mapped[datetime | None]` (`timestamptz`)
- `deleted_by: Mapped[uuid.UUID | None]`
- an `is_deleted` property

`deleted_by` has no foreign key:
- the mixin can be used on any table, including `users` (where an FK would be self-referential and order-dependent);
- it can be tested before `users` exists;
- system actors are allowed (`NULL`);
- it matches the "actor" column the audit trail (US-00.3) will need.

*Alternative considered:* `ForeignKey("users.id")`. Rejected: it couples every table to `users` and can't be tested in this change.

### D2. Global read filter via `do_orm_execute` + `with_loader_criteria`
A `Session`-level event listener checks `orm_execute_state.is_select`, and unless the `include_deleted=True` execution option is set, it adds `with_loader_criteria(SoftDeleteMixin, lambda cls: cls.deleted_at.is_(None), include_aliases=True)`.
- This is SQLAlchemy's documented recipe for global filters. It covers `select()`, `session.get()`, joins, and relationship lazy and eager loads, which is what the spec's "related records" scenario requires.
- The listener is registered on the sync `sqlalchemy.orm.Session` class, which `AsyncSession` wraps. That way it applies to sessions from `Database` **and** to the transactional sessions that tests build themselves.
- Registration happens at import time of `app/infrastructure/db/soft_delete.py`, which `app/infrastructure/db/models.py` imports. The app, Alembic, and tests all load `models.py`, so the listener is always active.

To read **only** deleted rows, use `include_deleted=True` plus an explicit `deleted_at IS NOT NULL` filter. The repository wraps this.

*Alternative considered:* a filter in the repository base class only. Rejected: it's easy to bypass with a hand-written query or a relationship load, and a missed filter would expose deleted medical data.

### D3. Runtime hard-delete guard (two hooks)
- `before_flush`: if `session.deleted` contains any `SoftDeleteMixin` instance, raise `HardDeleteForbiddenError`.
- `do_orm_execute`: if `orm_execute_state.is_delete` and the statement's target mapper is a `SoftDeleteMixin` subclass, raise `HardDeleteForbiddenError`.

`HardDeleteForbiddenError` is an infrastructure exception, not an `AppError`. The existing unexpected-error handler turns it into a 500 response with the standard envelope and logs it, which is what a programming defect should produce. The `Database.session()` unit of work rolls back on the error.

### D4. Database trigger as the final safeguard
- The migration for this change creates one shared PL/pgSQL function, `prevent_hard_delete()`. It raises an exception unless `current_setting('recliniq.allow_hard_delete', true) = 'on'`.
- A helper, `app/infrastructure/db/migration_helpers.py::protect_from_hard_delete(table_name)`, emits `CREATE TRIGGER <table>_prevent_hard_delete BEFORE DELETE ON <table> FOR EACH ROW EXECUTE FUNCTION prevent_hard_delete()`. A matching `unprotect_from_hard_delete(table_name)` is used for downgrade. Feature migrations call these helpers.
- The maintenance override is used with `SET LOCAL recliniq.allow_hard_delete = 'on'`, so it only lasts for that transaction. No application code path sets it.

*Why a trigger rather than revoking DELETE privileges:* the local, CI, and app environments use a single database role, and migrations still need DDL. A per-table trigger works on any role and can be tested.

*Alternative considered:* `BEFORE DELETE ... FOR EACH STATEMENT`. Rejected: a row-level trigger also fires for deletes that `ON DELETE CASCADE` foreign keys trigger, which is the point.

### D5. Coverage tests that check every table
- **Unit test (metadata):** every `Table` in `Base.metadata` has `deleted_at` and `deleted_by` columns unless its name is in `SOFT_DELETE_EXEMPT_TABLES`, which starts empty and is defined in `soft_delete.py`. Each mapped class for such a table must subclass `SoftDeleteMixin`.
- **Integration test (database):** after migrating, every soft-deletable table in `Base.metadata` has the `*_prevent_hard_delete` trigger in `pg_trigger`.

These tests pass trivially today because no tables exist, and they start checking real tables when US-01.1 adds them. Behavior tests (the read filter, guard, trigger, and partial unique index) use test-only models and tables (D7).

### D6. Partial unique index helper
`soft_unique_index(name, *columns)` returns `Index(name, *columns, unique=True, postgresql_where=text("deleted_at IS NULL"))` for use in `__table_args__`. Alembic autogenerate already renders `postgresql_where`. Plain `UniqueConstraint` / `unique=True` on soft-deletable tables is discouraged by the documented convention; enforcing it with a test is a possible follow-up for US-00.4.

### D7. Testing with test-only models
- The test models (for example `Widget` and `WidgetPart`, with a relationship) are declared on a **separate** `DeclarativeBase` inside `tests/`, using the same mixin. They therefore never enter `Base.metadata`, migrations, or the drift check.
- **Unit tests** (no database): use `select(...).compile()` or a `before_cursor_execute` capture to show the criteria are applied, and check that the guard raises before any SQL is sent.
- **Integration tests:** create the test tables inside the rolled-back test transaction (`run_sync(TestBase.metadata.create_all)`), attach the trigger with the same SQL the helper emits, then exercise the scenarios: soft delete and lookup, a relationship load, restore, a raw `DELETE` being rejected, the override, and partial unique index re-creation. PostgreSQL DDL is transactional, so everything disappears on rollback.

### D8. Repository base
`SoftDeleteRepository[T: SoftDeleteMixin]` in `app/infrastructure/db/repository.py` provides:
- `get(id, *, include_deleted=False)`
- `list_deleted()`
- `soft_delete(entity, actor_id: UUID | None)`, which does nothing if the entity is already deleted
- `restore(entity)`, which does nothing if the entity is active

Timestamps use `datetime.now(UTC)`. Feature repositories subclass it and implement their application ports. Because application ports are feature-specific, no generic port is added to `application/` now.

### D9. Default for short-lived tables (resolves the open question from exploration)
Ephemeral tables, such as US-01.1's email verification tokens, also use the mixin. The issue says "all tables", and soft-deleted tokens remain available for audit. The exemption list exists for future exceptions that have a documented reason.

## Risks / Trade-offs

- [The global filter feels "magic", and someone can't see deleted rows when debugging] → the explicit `include_deleted` option, documented in `backend/README.md` and `CLAUDE.md`.
- [`with_loader_criteria` with a lambda is cached per class. Using closures over outside variables breaks the statement cache] → the lambda refers only to `cls`. A unit test checks the compiled SQL.
- [Raw SQL via `text()` skips the ORM filter] → accepted; the trigger still blocks deletes. Raw reads are a code-review concern, and US-00.4's architecture checks can flag `text(` outside infrastructure.
- [A feature migration forgets `protect_from_hard_delete`] → the D5 integration test fails in CI.
- [Partial unique indexes can't be the target of `ON CONFLICT (cols)` without repeating the predicate] → document it; upserts must use `ON CONFLICT (cols) WHERE deleted_at IS NULL`.
- [No `deleted_by` FK, so it may point at a non-existent user] → accepted (D1). The audit trail can reconcile.

## Migration Plan

- One new Alembic revision after the baseline. It creates `prevent_hard_delete()`, and its downgrade drops it. No tables change.
- Rollback: `alembic downgrade -1`. No data is affected, since there are no application tables yet.
- The `local-dev-environment` and CI flows are unchanged; the migration runs at stack start and in CI as it does today.
