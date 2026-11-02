"""Opt-in local mock notifications, idempotent delivery history."""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_preferences",
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("language IN ('en','hi')"),
    )
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("record_id", sa.String(36), sa.ForeignKey("health_records.id"), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("body", sa.String(500), nullable=False),
        sa.Column("service_day", sa.Date(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("patient_id", "record_id", "record_version", "channel", "service_day"),
    )
    op.create_index("ix_notification_deliveries_patient_id", "notification_deliveries", ["patient_id"])


def downgrade():
    op.drop_table("notification_deliveries")
    op.drop_table("notification_preferences")
