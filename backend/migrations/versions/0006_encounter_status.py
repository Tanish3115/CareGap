"""Retain entered-in-error consultations as attributed revisions."""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    # A column-local check avoids rebuilding a SQLite table referenced by source links.
    op.add_column(
        "encounter_revisions",
        sa.Column(
            "status",
            sa.String(20),
            sa.CheckConstraint(
                "status IN ('active', 'entered_in_error')", name="ck_encounter_revision_status"
            ),
            nullable=False,
            server_default="active",
        ),
    )


def downgrade():
    op.drop_column("encounter_revisions", "status")
