"""Soft delete against real PostgreSQL: repository API, trigger, and partial unique indexes.

The test-only tables are created inside each test's rolled-back transaction (PostgreSQL DDL is
transactional), so they never persist and never touch migrations.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.infrastructure.db.migration_helpers import protect_sql
from app.infrastructure.db.models import Base
from app.infrastructure.db.repository import SoftDeleteRepository
from app.infrastructure.db.soft_delete import INCLUDE_DELETED, SOFT_DELETE_EXEMPT_TABLES
from tests.soft_delete_models import Widget, WidgetBase, WidgetPart


class WidgetRepository(SoftDeleteRepository[Widget]):
    model = Widget


class WidgetPartRepository(SoftDeleteRepository[WidgetPart]):
    model = WidgetPart


async def unprotected_tables(session: AsyncSession, tables: list[str]) -> list[str]:
    """Tables among ``tables`` that lack the hard-delete trigger."""
    rows = await session.execute(
        text(
            "SELECT c.relname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE NOT t.tgisinternal AND t.tgname = c.relname || '_prevent_hard_delete'"
        )
    )
    protected = {row[0] for row in rows}
    return sorted(set(tables) - protected)


@pytest.fixture
async def session(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    await db_session.run_sync(lambda s: WidgetBase.metadata.create_all(s.connection()))
    for table in WidgetBase.metadata.tables:
        await db_session.execute(text(protect_sql(table)))
    yield db_session


@pytest.fixture
def repo(session: AsyncSession) -> WidgetRepository:
    return WidgetRepository(session)


async def _widget_with_part(session: AsyncSession, code: str = "w-1") -> Widget:
    widget = Widget(code=code)
    session.add(widget)
    await session.flush()
    session.add(WidgetPart(widget_id=widget.id, name="part"))
    await session.flush()
    return widget


async def _raw_deleted_columns(
    session: AsyncSession, table: str, row_id: uuid.UUID
) -> tuple[Any, ...]:
    row = await session.execute(
        text(f"SELECT deleted_at, deleted_by FROM {table} WHERE id = :id"),  # noqa: S608
        {"id": row_id},
    )
    return tuple(row.one())


# --- Soft delete, exclusion, explicit access, restore -----------------------------------


async def test_soft_delete_keeps_row_and_records_actor(
    session: AsyncSession, repo: WidgetRepository
) -> None:
    widget = await _widget_with_part(session)
    actor = uuid.uuid4()

    await repo.soft_delete(widget, actor)

    deleted_at, deleted_by = await _raw_deleted_columns(session, "test_widgets", widget.id)
    assert deleted_at is not None
    assert deleted_by == actor


async def test_system_actor_leaves_deleted_by_null(
    session: AsyncSession, repo: WidgetRepository
) -> None:
    widget = await _widget_with_part(session)
    await repo.soft_delete(widget, None)
    deleted_at, deleted_by = await _raw_deleted_columns(session, "test_widgets", widget.id)
    assert deleted_at is not None
    assert deleted_by is None


async def test_deleting_again_keeps_original_values(
    session: AsyncSession, repo: WidgetRepository
) -> None:
    widget = await _widget_with_part(session)
    first_actor = uuid.uuid4()
    await repo.soft_delete(widget, first_actor)
    original = await _raw_deleted_columns(session, "test_widgets", widget.id)

    await repo.soft_delete(widget, uuid.uuid4())

    assert await _raw_deleted_columns(session, "test_widgets", widget.id) == original
    assert original[1] == first_actor


async def test_deleted_rows_are_hidden_by_default(
    session: AsyncSession, repo: WidgetRepository
) -> None:
    kept = await _widget_with_part(session, "kept")
    gone = await _widget_with_part(session, "gone")
    await repo.soft_delete(gone, uuid.uuid4())

    assert await repo.get(gone.id) is None
    assert await repo.get(kept.id) is kept
    codes = (await session.scalars(select(Widget.code))).all()
    assert codes == ["kept"]


async def test_relationship_load_hides_deleted_children(session: AsyncSession) -> None:
    widget = await _widget_with_part(session)
    removed = WidgetPart(widget_id=widget.id, name="removed")
    session.add(removed)
    await session.flush()
    await WidgetPartRepository(session).soft_delete(removed, None)
    session.expunge_all()

    loaded = await session.scalar(
        select(Widget).where(Widget.id == widget.id).options(selectinload(Widget.parts))
    )
    assert loaded is not None
    assert [part.name for part in loaded.parts] == ["part"]


async def test_explicit_access_to_deleted_rows(
    session: AsyncSession, repo: WidgetRepository
) -> None:
    await _widget_with_part(session, "kept")
    gone = await _widget_with_part(session, "gone")
    actor = uuid.uuid4()
    await repo.soft_delete(gone, actor)

    deleted = await repo.list_deleted()
    assert [w.code for w in deleted] == ["gone"]
    assert deleted[0].deleted_at is not None
    assert deleted[0].deleted_by == actor

    found = await repo.get(gone.id, include_deleted=True)
    assert found is gone


async def test_restore_makes_row_visible_again(
    session: AsyncSession, repo: WidgetRepository
) -> None:
    widget = await _widget_with_part(session)
    await repo.soft_delete(widget, uuid.uuid4())

    await repo.restore(widget)

    assert await _raw_deleted_columns(session, "test_widgets", widget.id) == (None, None)
    assert await repo.get(widget.id) is widget


async def test_restoring_active_row_changes_nothing(
    session: AsyncSession, repo: WidgetRepository
) -> None:
    widget = await _widget_with_part(session)
    await repo.restore(widget)
    assert await _raw_deleted_columns(session, "test_widgets", widget.id) == (None, None)


async def test_soft_delete_does_not_cascade(session: AsyncSession, repo: WidgetRepository) -> None:
    widget = await _widget_with_part(session)
    await repo.soft_delete(widget, uuid.uuid4())

    parts = (
        await session.scalars(
            select(WidgetPart)
            .where(WidgetPart.widget_id == widget.id)
            .execution_options(**{INCLUDE_DELETED: True})
        )
    ).all()
    assert len(parts) == 1
    assert parts[0].deleted_at is None
    assert parts[0].deleted_by is None


# --- Database trigger -------------------------------------------------------------------


async def test_raw_delete_is_rejected_by_database(session: AsyncSession) -> None:
    widget = await _widget_with_part(session)

    with pytest.raises(DBAPIError, match="Hard delete on table"):
        async with session.begin_nested():
            await session.execute(text("DELETE FROM test_widget_parts"))

    count = await session.scalar(text("SELECT count(*) FROM test_widget_parts"))
    assert count == 1
    assert await _raw_deleted_columns(session, "test_widgets", widget.id) == (None, None)


async def test_maintenance_override_allows_delete_in_transaction(session: AsyncSession) -> None:
    await _widget_with_part(session)

    await session.execute(text("SET LOCAL recliniq.allow_hard_delete = 'on'"))
    await session.execute(text("DELETE FROM test_widget_parts"))

    assert await session.scalar(text("SELECT count(*) FROM test_widget_parts")) == 0


async def test_every_soft_deletable_table_has_the_trigger(db_session: AsyncSession) -> None:
    soft_deletable = [
        name
        for name, table in Base.metadata.tables.items()
        if "deleted_at" in table.c and name not in SOFT_DELETE_EXEMPT_TABLES
    ]
    missing = await unprotected_tables(db_session, soft_deletable)
    assert missing == [], f"call protect_from_hard_delete() in the migration for: {missing}"


async def test_unprotected_table_is_detected(db_session: AsyncSession) -> None:
    await db_session.run_sync(lambda s: WidgetBase.metadata.create_all(s.connection()))
    assert await unprotected_tables(db_session, ["test_widgets"]) == ["test_widgets"]

    await db_session.execute(text(protect_sql("test_widgets")))
    assert await unprotected_tables(db_session, ["test_widgets"]) == []


# --- Partial unique index ---------------------------------------------------------------


async def test_unique_value_can_be_reused_after_soft_delete(
    session: AsyncSession, repo: WidgetRepository
) -> None:
    old = await _widget_with_part(session, "dup")
    await repo.soft_delete(old, uuid.uuid4())

    session.add(Widget(code="dup"))
    await session.flush()  # accepted: the deleted row doesn't count

    codes = (await session.scalars(select(Widget.code))).all()
    assert codes == ["dup"]


async def test_duplicate_among_active_rows_is_rejected(session: AsyncSession) -> None:
    await _widget_with_part(session, "dup")

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(Widget(code="dup"))
            await session.flush()
