"""schedule hours and exceptions"""

from alembic import op
import sqlalchemy as sa

revision = "002_schedule"
down_revision = "001_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_hours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("practitioner_id", sa.Integer(), sa.ForeignKey("practitioners.id"), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
    )
    op.create_index("ix_weekly_hours_tenant_id", "weekly_hours", ["tenant_id"])
    op.create_index("ix_weekly_hours_practitioner_id", "weekly_hours", ["practitioner_id"])
    op.create_table(
        "schedule_exceptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("practitioner_id", sa.Integer(), sa.ForeignKey("practitioners.id"), nullable=False),
        sa.Column("closed_on", sa.Date(), nullable=True),
        sa.Column("block_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("block_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(200)),
    )
    op.create_index("ix_schedule_exceptions_tenant_id", "schedule_exceptions", ["tenant_id"])
    op.create_index("ix_schedule_exceptions_practitioner_id", "schedule_exceptions", ["practitioner_id"])


def downgrade() -> None:
    op.drop_table("schedule_exceptions")
    op.drop_table("weekly_hours")
