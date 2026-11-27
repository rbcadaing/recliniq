"""Soft-delete behavior without PostgreSQL.

Uses an in-memory SQLite engine with a sync ``Session``: the listeners are registered on the ORM
``Session`` class, so they behave the same way as on the app's PostgreSQL ``AsyncSession``.
PostgreSQL-only behavior (trigger, partial unique index) is covered by integration tests.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session, aliased, joinedload, selectinload
from sqlalchemy.schema import CreateIndex

from app.infrastructure.db.migration_helpers import protect_sql, trigger_name, unprotect_sql
from app.infrastructure.db.models import Base
from app.infrastructure.db.soft_delete import INCLUDE_DELETED, HardDeleteForbiddenError
from tests.soft_delete_models import Widget, WidgetBase, WidgetPart


@pytest.fixture
def statements() -> list[str]:
    return []


@pytest.fixture
def session(statements: list[str]) -> Iterator[Session]:
    engine = create_engine("sqlite://")
    WidgetBase.metadata.create_all(engine)

    def capture(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _deleted() -> dict[str, Any]:
    return {"deleted_at": datetime.now(UTC)}


@pytest.fixture
def seeded(session: Session) -> dict[str, Any]:
    """One active widget with an active and a deleted part, and one deleted widget."""
    active = Widget(code="active")
    gone = Widget(code="gone", **_deleted())
    session.add_all([active, gone])
    session.flush()
    session.add_all(
        [
            WidgetPart(widget_id=active.id, name="kept"),
            WidgetPart(widget_id=active.id, name="removed", **_deleted()),
        ]
    )
    session.commit()
    ids = {"active": active.id, "gone": gone.id}
    session.expunge_all()  # later reads must hit the database, not the identity map
    return ids


# --- Mixin and helpers ----------------------------------------------------------------


def test_new_records_are_active(session: Session) -> None:
    widget = Widget(code="new")
    session.add(widget)
    session.commit()
    assert widget.deleted_at is None
    assert widget.deleted_by is None
    assert widget.is_deleted is False


def test_soft_unique_index_only_applies_to_active_rows() -> None:
    index = next(iter(Widget.__table__.indexes))
    ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
    assert ddl.startswith("CREATE UNIQUE INDEX")
    assert "WHERE deleted_at IS NULL" in ddl


def test_test_models_stay_out_of_app_metadata() -> None:
    assert "test_widgets" not in Base.metadata.tables
    assert "test_widget_parts" not in Base.metadata.tables


def test_migration_helper_sql() -> None:
    assert trigger_name("users") == "users_prevent_hard_delete"
    assert protect_sql("users") == (
        'CREATE TRIGGER "users_prevent_hard_delete" BEFORE DELETE ON "users" '
        "FOR EACH ROW EXECUTE FUNCTION prevent_hard_delete()"
    )
    assert unprotect_sql("users") == 'DROP TRIGGER IF EXISTS "users_prevent_hard_delete" ON "users"'


# --- Reads exclude deleted rows by default ----------------------------------------------


def test_select_excludes_deleted(session: Session, seeded: dict[str, Any]) -> None:
    codes = session.scalars(select(Widget.code)).all()
    assert codes == ["active"]
    assert session.get(Widget, seeded["gone"]) is None


def test_criteria_appear_in_emitted_sql(
    session: Session, seeded: dict[str, Any], statements: list[str]
) -> None:
    statements.clear()
    session.scalars(select(Widget)).all()
    assert "deleted_at IS NULL" in statements[-1]


def test_join_and_alias_exclude_deleted(session: Session, seeded: dict[str, Any]) -> None:
    joined = session.scalars(
        select(WidgetPart.name).join(WidgetPart.widget).where(Widget.code == "active")
    ).all()
    assert joined == ["kept"]

    part = aliased(WidgetPart)
    aliased_names = session.scalars(select(part.name)).all()
    assert aliased_names == ["kept"]


@pytest.mark.parametrize("loader", [selectinload, joinedload])
def test_relationship_loads_exclude_deleted_children(
    session: Session, seeded: dict[str, Any], loader: Any
) -> None:
    widget = session.scalars(select(Widget).options(loader(Widget.parts))).unique().one()
    assert [part.name for part in widget.parts] == ["kept"]


def test_include_deleted_opt_out(session: Session, seeded: dict[str, Any]) -> None:
    codes = session.scalars(
        select(Widget.code).order_by(Widget.code).execution_options(**{INCLUDE_DELETED: True})
    ).all()
    assert codes == ["active", "gone"]
    widget = session.get(Widget, seeded["gone"], execution_options={INCLUDE_DELETED: True})
    assert widget is not None
    assert widget.is_deleted


# --- Hard deletes are rejected before any SQL is sent -----------------------------------


def test_session_delete_is_rejected(
    session: Session, seeded: dict[str, Any], statements: list[str]
) -> None:
    widget = session.get(Widget, seeded["active"])
    statements.clear()
    session.delete(widget)
    with pytest.raises(HardDeleteForbiddenError, match="Widget"):
        session.flush()
    assert not any(s.lstrip().upper().startswith("DELETE") for s in statements)


def test_bulk_delete_is_rejected(
    session: Session, seeded: dict[str, Any], statements: list[str]
) -> None:
    statements.clear()
    with pytest.raises(HardDeleteForbiddenError, match="Widget"):
        session.execute(delete(Widget).where(Widget.code == "active"))
    assert not any(s.lstrip().upper().startswith("DELETE") for s in statements)
    session.rollback()
    assert session.scalars(select(Widget.code)).all() == ["active"]


async def test_hard_delete_attempt_returns_500_envelope(app: FastAPI, client: AsyncClient) -> None:
    @app.delete("/api/v1/_test/widget")
    async def hard_delete() -> None:
        raise HardDeleteForbiddenError("Deleting Widget is not allowed; soft-delete instead.")

    response = await client.delete("/api/v1/_test/widget", headers={"X-Request-ID": "hd-1"})
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "internal_error"
    assert error["request_id"] == "hd-1"
    assert "Widget" not in response.text
