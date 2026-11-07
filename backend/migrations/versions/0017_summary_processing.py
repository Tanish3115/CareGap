"""Explicit patient opt-in to a named summary processor. Default remains off."""

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "summary_processing_consents",
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("provider_reference", sa.String(200), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_summary_consent_version"),
    )


def downgrade():
    op.drop_table("summary_processing_consents")
