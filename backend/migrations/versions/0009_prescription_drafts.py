"""Source-bound prescription revisions and historical documented medication entries."""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "medical_documents",
        sa.Column(
            "prescription_version",
            sa.Integer(),
            sa.CheckConstraint("prescription_version >= 0", name="ck_document_prescription_version"),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_table(
        "prescription_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("medical_documents.id"), nullable=False),
        sa.Column(
            "source_review_id", sa.String(36), sa.ForeignKey("document_review_revisions.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("extractor_version", sa.String(40), nullable=False),
        sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("author_role", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "version"),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("state IN ('draft','clinician_confirmed')"),
    )
    op.create_index("ix_prescription_revisions_document_id", "prescription_revisions", ["document_id"])
    columns = [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("medical_documents.id"), nullable=False),
        sa.Column(
            "prescription_revision_id",
            sa.String(36),
            sa.ForeignKey("prescription_revisions.id"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
    ]
    columns += [
        sa.Column(name, sa.String(500), nullable=True)
        for name in ("strength", "dose", "route", "frequency", "duration", "instructions")
    ]
    op.create_table(
        "medication_entries",
        *columns,
        sa.Column("needs_clarification", sa.Boolean(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("prescription_revision_id", "row_number"),
    )
    for name in ("patient_id", "document_id", "prescription_revision_id"):
        op.create_index(f"ix_medication_entries_{name}", "medication_entries", [name])


def downgrade():
    op.drop_table("medication_entries")
    op.drop_table("prescription_revisions")
    op.drop_column("medical_documents", "prescription_version")
