"""Immutable original FHIR import sources and revision links."""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fhir_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("original", sa.JSON(), nullable=False),
        sa.Column("imported_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("patient_id", "sha256"),
    )
    op.create_index("ix_fhir_imports_patient_id", "fhir_imports", ["patient_id"])
    op.create_table(
        "fhir_import_links",
        sa.Column("revision_id", sa.String(36), sa.ForeignKey("health_revisions.id"), primary_key=True),
        sa.Column("import_id", sa.String(36), sa.ForeignKey("fhir_imports.id"), nullable=False),
    )
    op.create_index("ix_fhir_import_links_import_id", "fhir_import_links", ["import_id"])


def downgrade():
    op.drop_table("fhir_import_links")
    op.drop_table("fhir_imports")
