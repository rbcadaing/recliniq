"""in-app alerts and email outbox"""

from alembic import op
import sqlalchemy as sa

revision = "005_notifications"
down_revision = "004_visits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "in_app_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_in_app_alerts_tenant_id", "in_app_alerts", ["tenant_id"])
    op.create_index("ix_in_app_alerts_user_id", "in_app_alerts", ["user_id"])
    op.create_table(
        "email_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("to_email", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_email_outbox_tenant_id", "email_outbox", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("email_outbox")
    op.drop_table("in_app_alerts")
