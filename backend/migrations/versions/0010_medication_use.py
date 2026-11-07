"""Patient-reported use and clinician reconciliation history."""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "medication_uses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("review_version >= 0"),
    )
    op.create_index("ix_medication_uses_patient_id", "medication_uses", ["patient_id"])
    op.create_table(
        "medication_use_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("medication_use_id", sa.String(36), sa.ForeignKey("medication_uses.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("dose", sa.String(500)),
        sa.Column("frequency", sa.String(500)),
        sa.Column("use_status", sa.String(20), nullable=False),
        sa.Column("reported_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.Column("source_entry_id", sa.String(36), sa.ForeignKey("medication_entries.id")),
        sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("medication_use_id", "version"),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("use_status IN ('taking','not_taking','unknown')"),
    )
    op.create_index(
        "ix_medication_use_revisions_medication_use_id", "medication_use_revisions", ["medication_use_id"]
    )
    op.create_table(
        "medication_reconciliations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("medication_use_id", sa.String(36), sa.ForeignKey("medication_uses.id"), nullable=False),
        sa.Column(
            "report_revision_id", sa.String(36), sa.ForeignKey("medication_use_revisions.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("assessment", sa.String(30), nullable=False),
        sa.Column("note", sa.String(2000), nullable=False),
        sa.Column("source_snapshot", sa.JSON(), nullable=True),
        sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("medication_use_id", "version"),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("assessment IN ('account_reviewed','discrepancy','needs_clarification')"),
    )
    op.create_index(
        "ix_medication_reconciliations_medication_use_id", "medication_reconciliations", ["medication_use_id"]
    )


def downgrade():
    op.drop_table("medication_reconciliations")
    op.drop_table("medication_use_revisions")
    op.drop_table("medication_uses")
