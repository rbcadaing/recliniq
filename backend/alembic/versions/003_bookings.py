"""bookings with partial unique booked slot"""

from alembic import op
import sqlalchemy as sa

revision = "003_bookings"
down_revision = "002_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("practitioner_id", sa.Integer(), sa.ForeignKey("practitioners.id"), nullable=False),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cancelled_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_bookings_tenant_id", "bookings", ["tenant_id"])
    op.create_index("ix_bookings_practitioner_id", "bookings", ["practitioner_id"])
    op.create_index("ix_bookings_patient_id", "bookings", ["patient_id"])
    op.create_index(
        "uq_booking_slot_booked",
        "bookings",
        ["practitioner_id", "starts_at"],
        unique=True,
        postgresql_where=sa.text("status = 'booked'"),
    )


def downgrade() -> None:
    op.drop_table("bookings")
