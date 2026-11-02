"""Keep notification preferences while adding the six requested languages."""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def replace_preferences(languages):
    # No tables reference preferences; deliveries reference the patient/care event.
    target = "notification_preferences_language_upgrade"
    op.create_table(
        target,
        sa.Column("patient_id", sa.String(36), sa.ForeignKey("patients.id"), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(5), nullable=False),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint(
            "language IN (" + ",".join(repr(language) for language in languages) + ")",
            name="ck_notification_language",
        ),
    )
    columns = "patient_id,version,enabled,channels,language"
    op.execute(sa.text(f"INSERT INTO {target} ({columns}) SELECT {columns} FROM notification_preferences"))
    op.drop_table("notification_preferences")
    op.rename_table(target, "notification_preferences")


def upgrade():
    replace_preferences(("en", "hi", "kn", "te", "ta", "ml"))


def downgrade():
    count = (
        op.get_bind()
        .execute(sa.text("SELECT COUNT(*) FROM notification_preferences WHERE language NOT IN ('en','hi')"))
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            "Downgrade would discard language preferences. Change affected preferences explicitly before retrying."
        )
    replace_preferences(("en", "hi"))
