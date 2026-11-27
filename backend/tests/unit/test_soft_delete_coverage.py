"""Every application table must be soft-deletable (US-00.2).

Trivially passes until the first real table exists; from then on it names any table that is
missing the soft-delete columns or whose mapped class doesn't use ``SoftDeleteMixin``.
"""

from sqlalchemy import Column, Integer, MetaData, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.orm import registry as Registry  # noqa: N812

from app.infrastructure.db.base import SoftDeleteMixin
from app.infrastructure.db.models import Base
from app.infrastructure.db.soft_delete import SOFT_DELETE_EXEMPT_TABLES

REQUIRED_COLUMNS = ("deleted_at", "deleted_by")


def soft_delete_violations(metadata: MetaData, registry: Registry) -> list[str]:
    problems = []
    for name, table in metadata.tables.items():
        if name in SOFT_DELETE_EXEMPT_TABLES:
            continue
        missing = [column for column in REQUIRED_COLUMNS if column not in table.c]
        if missing:
            problems.append(f"{name}: missing columns {', '.join(missing)}")
    for mapper in registry.mappers:
        table_names = {t.name for t in mapper.tables}
        if table_names & SOFT_DELETE_EXEMPT_TABLES:
            continue
        if not issubclass(mapper.class_, SoftDeleteMixin):
            problems.append(f"{mapper.class_.__name__}: does not use SoftDeleteMixin")
    return problems


def test_every_application_table_is_soft_deletable() -> None:
    assert soft_delete_violations(Base.metadata, Base.registry) == []


def test_checker_names_a_table_without_soft_delete_columns() -> None:
    metadata = MetaData()
    Table("plain", metadata, Column("id", Integer, primary_key=True))

    assert soft_delete_violations(metadata, Registry()) == [
        "plain: missing columns deleted_at, deleted_by"
    ]


def test_checker_names_a_model_without_the_mixin() -> None:
    class ScratchBase(DeclarativeBase):
        pass

    class Plain(ScratchBase):
        __tablename__ = "plain"
        id: Mapped[int] = mapped_column(primary_key=True)

    assert soft_delete_violations(ScratchBase.metadata, ScratchBase.registry) == [
        "plain: missing columns deleted_at, deleted_by",
        "Plain: does not use SoftDeleteMixin",
    ]
