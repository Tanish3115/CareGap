"""Durable, leased document-processing jobs with bounded retries."""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "document_processing_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("medical_documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_token", sa.String(36)),
        sa.Column("lease_until", sa.DateTime()),
        sa.Column("error_code", sa.String(40)),
        sa.Column("result", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("finished_at", sa.DateTime()),
        sa.CheckConstraint("status IN ('queued','processing','succeeded','failed')"),
        sa.CheckConstraint("attempts >= 0 AND attempts <= 3"),
        sa.CheckConstraint("status != 'processing' OR (lease_token IS NOT NULL AND lease_until IS NOT NULL)"),
    )
    op.create_index(
        "ix_processing_claim", "document_processing_jobs", ["status", "lease_until", "created_at"]
    )


def downgrade():
    op.drop_table("document_processing_jobs")
