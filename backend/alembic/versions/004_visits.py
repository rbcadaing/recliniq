"""visit records and documents"""

from alembic import op
import sqlalchemy as sa

revision = "004_visits"
down_revision = "003_bookings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "visit_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("booking_id", sa.Integer(), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_visit_records_tenant_id", "visit_records", ["tenant_id"])
    op.create_unique_constraint("uq_visit_records_booking_id", "visit_records", ["booking_id"])
    op.create_table(
        "visit_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("visit_record_id", sa.Integer(), sa.ForeignKey("visit_records.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("stored_name", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_visit_documents_tenant_id", "visit_documents", ["tenant_id"])
    op.create_index("ix_visit_documents_visit_record_id", "visit_documents", ["visit_record_id"])


def downgrade() -> None:
    op.drop_table("visit_documents")
    op.drop_table("visit_records")
