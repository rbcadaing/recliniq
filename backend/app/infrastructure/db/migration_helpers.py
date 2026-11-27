"""Helpers for Alembic migrations.

Every migration that creates a soft-deletable table must call ``protect_from_hard_delete`` for
it in ``upgrade()`` (and ``unprotect_from_hard_delete`` in ``downgrade()`` before dropping it).
The trigger function ``prevent_hard_delete()`` is created by the soft-delete foundation
migration. A test fails if a soft-deletable table in the migrated database lacks the trigger.

Maintenance override (never set by application code): inside a transaction, run
``SET LOCAL recliniq.allow_hard_delete = 'on'`` before the ``DELETE``.
"""

from alembic import op

ALLOW_HARD_DELETE_SETTING = "recliniq.allow_hard_delete"


def trigger_name(table: str) -> str:
    return f"{table}_prevent_hard_delete"


def protect_sql(table: str) -> str:
    return (
        f'CREATE TRIGGER "{trigger_name(table)}" BEFORE DELETE ON "{table}" '
        "FOR EACH ROW EXECUTE FUNCTION prevent_hard_delete()"
    )


def unprotect_sql(table: str) -> str:
    return f'DROP TRIGGER IF EXISTS "{trigger_name(table)}" ON "{table}"'


def protect_from_hard_delete(table: str) -> None:
    op.execute(protect_sql(table))


def unprotect_from_hard_delete(table: str) -> None:
    op.execute(unprotect_sql(table))
