"""Durable private-file cleanup after patient-owned document deletion."""

from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "file_deletions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("document_id", sa.String(36), unique=True, nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("storage_backend", sa.String(10), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('pending','done')"),
        sa.CheckConstraint("attempts >= 0"),
    )
    op.create_index("ix_file_deletions_patient_id", "file_deletions", ["patient_id"])


def downgrade():
    if (
        op.get_bind()
        .execute(sa.text("SELECT COUNT(*) FROM file_deletions WHERE status = 'pending'"))
        .scalar_one()
    ):
        raise RuntimeError("Finish pending document file cleanup before downgrading")
    op.drop_table("file_deletions")
