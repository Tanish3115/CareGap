"""Per-document storage routing and attributed source-transcription reviews."""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "medical_documents",
        sa.Column(
            "storage_backend",
            sa.String(10),
            sa.CheckConstraint("storage_backend IN ('local','s3')", name="ck_document_storage_backend"),
            nullable=False,
            server_default="local",
        ),
    )
    op.add_column(
        "medical_documents",
        sa.Column(
            "review_version",
            sa.Integer(),
            sa.CheckConstraint("review_version >= 0", name="ck_document_review_version"),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_table(
        "document_review_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("medical_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "processing_job_id", sa.String(36), sa.ForeignKey("document_processing_jobs.id"), nullable=False
        ),
        sa.Column("processing_attempt", sa.Integer(), nullable=False),
        sa.Column("processor_version", sa.String(40), nullable=False),
        sa.Column("source_sha256", sa.String(64), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("reviewed_text", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewer_kind", sa.String(20), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "version"),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("reviewer_kind IN ('patient_reviewed','clinician_reviewed')"),
    )
    op.create_index("ix_document_review_revisions_document_id", "document_review_revisions", ["document_id"])


def downgrade():
    op.drop_table("document_review_revisions")
    op.drop_column("medical_documents", "review_version")
    op.drop_column("medical_documents", "storage_backend")
