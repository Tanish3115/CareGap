"""Baseline matching the original six-table application schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False), sa.Column("role", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False), sa.Column("phone", sa.String(50)),
        sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table("patients",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("date_of_birth", sa.Date()), sa.Column("gender", sa.String(20)), sa.Column("blood_group", sa.String(10)),
        sa.Column("emergency_contact", sa.String(100)), sa.Column("address", sa.Text()), sa.Column("abha_id", sa.String(50)),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_patients_abha_id", "patients", ["abha_id"])
    op.create_table("doctors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("license_number", sa.String(100), nullable=False), sa.Column("specialization", sa.String(100), nullable=False),
        sa.Column("hospital_affiliation", sa.String(200)), sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_doctors_license_number", "doctors", ["license_number"], unique=True)
    op.create_table("medical_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploader_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False), sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False), sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False), sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("sha256_hash", sa.String(64), nullable=False), sa.Column("status", sa.String(50), nullable=False),
        sa.Column("clinical_date", sa.Date()), sa.Column("metadata_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_medical_documents_patient_id", "medical_documents", ["patient_id"])
    op.create_table("consent_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("doctor_id", sa.String(36), sa.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False), sa.Column("purpose", sa.String(255), nullable=False),
        sa.Column("valid_from", sa.DateTime(), nullable=False), sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False), sa.Column("revoked_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_consent_grants_patient_id", "consent_grants", ["patient_id"])
    op.create_index("ix_consent_grants_doctor_id", "consent_grants", ["doctor_id"])
    op.create_table("audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("patient_id", sa.String(36)), sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False), sa.Column("resource_id", sa.String(100)),
        sa.Column("ip_address", sa.String(50)), sa.Column("details", sa.Text()), sa.Column("created_at", sa.DateTime(), nullable=False))
    for column in ("actor_id", "patient_id", "created_at"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column])


def downgrade():
    for table in ("audit_logs", "consent_grants", "medical_documents", "doctors", "patients", "users"):
        op.drop_table(table)
