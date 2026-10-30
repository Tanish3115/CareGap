"""Revocable sessions, consent decisions and professional verification history."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("consent_grants", sa.Column("allow_upload", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("consent_grants", sa.Column("document_ids", sa.JSON(), nullable=True))
    op.create_table("auth_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False), sa.Column("revoked_at", sa.DateTime()))
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_table("access_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("doctor_id", sa.String(36), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False), sa.Column("purpose", sa.String(255), nullable=False),
        sa.Column("duration_hours", sa.Integer(), nullable=False), sa.Column("allow_upload", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime()), sa.Column("grant_id", sa.String(36), sa.ForeignKey("consent_grants.id")),
        sa.CheckConstraint("scope IN ('all', 'prescriptions_only', 'labs_only')"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'denied')"),
        sa.CheckConstraint("duration_hours >= 1 AND duration_hours <= 720"))
    op.create_index("ix_access_requests_patient_id", "access_requests", ["patient_id"])
    op.create_index("ix_access_requests_doctor_id", "access_requests", ["doctor_id"])
    op.create_index("uq_pending_access_request", "access_requests", ["patient_id", "doctor_id"], unique=True,
                    sqlite_where=sa.text("status = 'pending'"), postgresql_where=sa.text("status = 'pending'"))
    op.create_table("doctor_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("doctor_id", sa.String(36), sa.ForeignKey("doctors.id"), nullable=False),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("evidence_reference", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_doctor_verifications_doctor_id", "doctor_verifications", ["doctor_id"])


def downgrade():
    op.drop_table("doctor_verifications")
    op.drop_table("access_requests")
    op.drop_table("auth_sessions")
    op.drop_column("consent_grants", "document_ids")
    op.drop_column("consent_grants", "allow_upload")
