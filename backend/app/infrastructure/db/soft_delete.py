"""Session-wide soft-delete behavior.

Importing this module registers two listeners on every ORM ``Session`` (``AsyncSession`` wraps
one), so they apply to app sessions and test sessions alike:

* Reads: every ORM ``SELECT`` gets ``deleted_at IS NULL`` for soft-deletable models, including
  joins and relationship loads. Opt out per statement with
  ``.execution_options(include_deleted=True)``.
* Writes: physically deleting a soft-deletable entity (``session.delete`` or a bulk ``delete()``)
  raises ``HardDeleteForbiddenError`` before any SQL is sent. The database trigger installed by
  ``migration_helpers.protect_from_hard_delete`` is the last line of defense for raw SQL.
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.infrastructure.db.base import SoftDeleteMixin

INCLUDE_DELETED = "include_deleted"

# Application tables allowed to skip soft delete. Every entry needs a documented reason.
SOFT_DELETE_EXEMPT_TABLES: frozenset[str] = frozenset()


class HardDeleteForbiddenError(RuntimeError):
    """A code path tried to physically delete a soft-deletable row. This is a programming defect."""


@event.listens_for(Session, "do_orm_execute")
def _apply_soft_delete_rules(state: ORMExecuteState) -> None:
    mapper = state.bind_mapper
    if state.is_delete and mapper is not None and issubclass(mapper.class_, SoftDeleteMixin):
        raise HardDeleteForbiddenError(
            f"Bulk DELETE on {mapper.class_.__name__} is not allowed; soft-delete instead."
        )
    if (
        state.is_select
        and not state.is_column_load
        and not state.is_relationship_load
        and not state.execution_options.get(INCLUDE_DELETED, False)
    ):
        # The lambda must refer only to ``cls`` so SQLAlchemy can cache the criteria per class.
        # The criteria also propagate to relationship loads of the objects this query returns.
        state.statement = state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )


@event.listens_for(Session, "before_flush")
def _forbid_hard_delete(session: Session, flush_context: Any, instances: Any) -> None:
    for obj in session.deleted:
        if isinstance(obj, SoftDeleteMixin):
            raise HardDeleteForbiddenError(
                f"Deleting {type(obj).__name__} is not allowed; soft-delete instead."
            )
