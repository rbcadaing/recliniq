"""soft delete foundation

Creates the shared prevent_hard_delete() trigger function. Each migration that adds a
soft-deletable table attaches it with migration_helpers.protect_from_hard_delete(table).

Revision ID: cba523bd0fe0
Revises: 60d50daba8ca
Create Date: 2026-11-27 22:29:16.222837

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "cba523bd0fe0"
down_revision: Union[str, Sequence[str], None] = "60d50daba8ca"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Raises on any row DELETE unless a maintenance transaction has run
# SET LOCAL recliniq.allow_hard_delete = 'on'.
CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION prevent_hard_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('recliniq.allow_hard_delete', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'Hard delete on table "%" is not allowed; soft-delete instead.', TG_TABLE_NAME
        USING ERRCODE = 'restrict_violation';
END;
$$
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(CREATE_FUNCTION)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP FUNCTION IF EXISTS prevent_hard_delete()")
