## 1. Mixin and conventions

- [x] 1.1 Add `SoftDeleteMixin` (`deleted_at` timestamptz, `deleted_by` UUID with no FK, `is_deleted` property) to `app/infrastructure/db/base.py`, and verify with `uv run mypy`.
- [x] 1.2 Add `soft_unique_index(name, *columns)` (a partial unique index `WHERE deleted_at IS NULL`), and verify with a unit test that the compiled `CREATE INDEX` DDL contains the predicate.
- [x] 1.3 Create the test-only models in `tests/soft_delete_models.py` (`Widget` with a soft-unique `code`, and `WidgetPart` linked by a relationship) on a separate `DeclarativeBase`, and verify they are absent from `app.infrastructure.db.models.Base.metadata`.

## 2. Read filter and hard-delete guard

- [x] 2.1 Create `app/infrastructure/db/soft_delete.py` with `HardDeleteForbiddenError`, `SOFT_DELETE_EXEMPT_TABLES = frozenset()`, and the `do_orm_execute` listener registered on `sqlalchemy.orm.Session`. The listener adds `with_loader_criteria(SoftDeleteMixin, deleted_at IS NULL, include_aliases=True)` to selects unless `include_deleted=True` is set. Import the module from `app/infrastructure/db/models.py`. Verify with unit tests on the compiled SQL that a select, a join, and the `include_deleted` opt-out behave as expected.
- [x] 2.2 Add the hard-delete guard: a `before_flush` check on `session.deleted` and a `do_orm_execute` check for bulk deletes on soft-deletable mappers. Verify with unit tests that both raise `HardDeleteForbiddenError` before any SQL reaches the cursor.
- [x] 2.3 Verify with an API unit test that a route raising `HardDeleteForbiddenError` returns a 500 response in the standard error envelope with a `request_id`.

## 3. Repository base

- [x] 3.1 Add `SoftDeleteRepository[T]` in `app/infrastructure/db/repository.py` with `get(id, include_deleted=False)`, `list_deleted()`, `soft_delete(entity, actor_id)` (a no-op on an already-deleted entity), and `restore(entity)` (a no-op on an active entity). Verify with `uv run mypy`; behavior is tested in 5.x.

## 4. Database trigger and migration

- [x] 4.1 Add `app/infrastructure/db/migration_helpers.py` with `protect_from_hard_delete(table)` / `unprotect_from_hard_delete(table)`, and with the shared SQL for `prevent_hard_delete()` (it honors `SET LOCAL recliniq.allow_hard_delete = 'on'`). Verify with a unit test of the emitted SQL strings.
- [x] 4.2 Create the Alembic revision that creates `prevent_hard_delete()` on upgrade and drops it on downgrade. Verify that `uv run alembic upgrade head`, then `downgrade -1`, then `upgrade head` all succeed against the local database, and that the drift-check test still passes.

## 5. Integration tests (PostgreSQL)

- [x] 5.1 Add a fixture that creates the test-only tables inside the rolled-back test transaction and attaches the trigger through the helper's SQL. Verify that the tables don't exist after the test session ends.
- [x] 5.2 Test that a soft delete keeps the row and sets `deleted_at`/`deleted_by`, that deleting again keeps the original values, that lookups and lists exclude the deleted row, that the relationship load excludes deleted parts, that `include_deleted` and `list_deleted()` return it, that `restore()` brings it back, and that soft-deleting the parent leaves its children unchanged.
- [x] 5.3 Test that a raw `DELETE` against the test table raises a database error and leaves the row, and that the same `DELETE` succeeds after `SET LOCAL recliniq.allow_hard_delete = 'on'`.
- [x] 5.4 Test that re-creating a `Widget` with the `code` of a soft-deleted one succeeds, and that a duplicate among active rows raises an integrity error.
- [x] 5.5 Verify the full suite passes with `TEST_DATABASE_URL=... uv run pytest`.

## 6. Coverage guards for future tables

- [x] 6.1 Add a unit test asserting that every table in `Base.metadata` (excluding `SOFT_DELETE_EXEMPT_TABLES`) has `deleted_at` and `deleted_by` and is mapped by a `SoftDeleteMixin` subclass. Verify it fails when a temporary table without the columns is added to the metadata, then passes once it's removed.
- [x] 6.2 Add an integration test asserting that every soft-deletable table in `Base.metadata` has a `<table>_prevent_hard_delete` trigger in `pg_trigger`, with a failure message that names the table. Verify it passes against the migrated test database.

## 7. Documentation and checks

- [x] 7.1 Document in `backend/README.md`: the mixin, `include_deleted`, the repository API, `protect_from_hard_delete` in every new table's migration, `soft_unique_index` instead of plain unique constraints, `ON CONFLICT ... WHERE deleted_at IS NULL`, no automatic cascade, the exemption list, and the maintenance override. Add a short summary to `CLAUDE.md`. Verify by reading both files.
- [x] 7.2 Verify that `uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest` (with `TEST_DATABASE_URL`) passes. That's the same set CI runs.
