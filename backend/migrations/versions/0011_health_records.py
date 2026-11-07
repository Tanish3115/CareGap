"""Typed health records, source links and immutable revisions."""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "health_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint(
            "kind IN ('diagnosis','allergy','lab','appointment','referral','test','medication_order','dispensing','confirmed_use','intervention')"
        ),
    )
    for col in ("patient_id", "kind"):
        op.create_index(f"ix_health_records_{col}", "health_records", [col])
    op.create_table(
        "health_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("record_id", sa.String(36), sa.ForeignKey("health_records.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provenance", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("record_id", "version"),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("provenance IN ('patient_reported','clinician_recorded')"),
    )
    op.create_index("ix_health_revisions_record_id", "health_revisions", ["record_id"])
    op.create_table(
        "health_sources",
        sa.Column("revision_id", sa.String(36), sa.ForeignKey("health_revisions.id"), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("medical_documents.id"), primary_key=True),
    )


def downgrade():
    op.drop_table("health_sources")
    op.drop_table("health_revisions")
    op.drop_table("health_records")
