"""Source-bound prescription context; old medication entries remain unchanged."""

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("prescription_revisions", sa.Column("context", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("prescription_revisions", "context")
