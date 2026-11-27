"""Declarative base shared by all ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, MetaData, Uuid, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint names so Alembic autogenerate produces deterministic migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SoftDeleteMixin:
    """Rows are never physically removed: deleting sets ``deleted_at`` and ``deleted_by``.

    Every application table must use this mixin (see ``soft_delete.SOFT_DELETE_EXEMPT_TABLES``)
    and call ``migration_helpers.protect_from_hard_delete`` in the migration that creates it.
    ``deleted_by`` is the acting user's id (``None`` for system actions). It deliberately has no
    foreign key so the mixin works on any table, including ``users`` itself.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


def soft_unique_index(name: str, *columns: str) -> Index:
    """Unique index that only applies to rows that are not soft-deleted.

    Use this instead of ``unique=True`` / ``UniqueConstraint`` on soft-deletable tables, so a
    deleted row never blocks a new row with the same values. Upserts must repeat the predicate:
    ``ON CONFLICT (cols) WHERE deleted_at IS NULL``.
    """
    return Index(name, *columns, unique=True, postgresql_where=text("deleted_at IS NULL"))
