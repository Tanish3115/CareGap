"""Versioned encounters, source links, follow-ups and explicit clinical consent."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def identity_columns():
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version >= 1"),
    ]


def revision_columns(parent_column, parent_table):
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(parent_column, sa.String(36), sa.ForeignKey(f"{parent_table}.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provenance", sa.String(30), nullable=False),
        sa.Column("correction_reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(parent_column, "version"),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("provenance IN ('patient_reported', 'clinician_recorded')"),
    ]


def upgrade():
    for table in ("consent_grants", "access_requests"):
        op.add_column(
            table,
            sa.Column("include_clinical_records", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.add_column(
            table, sa.Column("allow_clinical_write", sa.Boolean(), nullable=False, server_default=sa.false())
        )
    op.create_table("encounters", *identity_columns())
    op.create_index("ix_encounters_patient_id", "encounters", ["patient_id"])
    op.create_table(
        "encounter_revisions",
        *revision_columns("encounter_id", "encounters"),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
    )
    op.create_index("ix_encounter_revisions_encounter_id", "encounter_revisions", ["encounter_id"])
    op.create_table(
        "encounter_sources",
        sa.Column("revision_id", sa.String(36), sa.ForeignKey("encounter_revisions.id"), primary_key=True),
        sa.Column("document_id", sa.String(36), sa.ForeignKey("medical_documents.id"), primary_key=True),
    )
    op.create_table(
        "follow_up_tasks",
        *identity_columns(),
        sa.Column("encounter_id", sa.String(36), sa.ForeignKey("encounters.id"), nullable=False),
    )
    op.create_index("ix_follow_up_tasks_patient_id", "follow_up_tasks", ["patient_id"])
    op.create_index("ix_follow_up_tasks_encounter_id", "follow_up_tasks", ["encounter_id"])
    op.create_table(
        "follow_up_revisions",
        *revision_columns("task_id", "follow_up_tasks"),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'completed', 'cancelled')"),
        sa.CheckConstraint("status = 'pending' OR outcome IS NOT NULL"),
    )
    op.create_index("ix_follow_up_revisions_task_id", "follow_up_revisions", ["task_id"])


def downgrade():
    op.drop_table("follow_up_revisions")
    op.drop_table("follow_up_tasks")
    op.drop_table("encounter_sources")
    op.drop_table("encounter_revisions")
    op.drop_table("encounters")
    for table in ("access_requests", "consent_grants"):
        op.drop_column(table, "allow_clinical_write")
        op.drop_column(table, "include_clinical_records")
