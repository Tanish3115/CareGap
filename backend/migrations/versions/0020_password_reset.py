"""Expiring, single-use password recovery tokens."""

from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "password_reset_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    if op.get_bind().dialect.name == "postgresql":
        # Supabase may grant new public-schema tables to its Data API roles by
        # default. Recovery credentials remain accessible only to the backend
        # table owner, matching the existing hosted application tables.
        op.execute("ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY")
        op.execute("REVOKE ALL ON TABLE password_reset_tokens FROM PUBLIC")
        op.execute(
            """
            DO $caregap$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL ON TABLE password_reset_tokens FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL ON TABLE password_reset_tokens FROM authenticated;
                END IF;
            END;
            $caregap$;
            """
        )


def downgrade():
    # Outstanding email links cease to work when password recovery is rolled back.
    op.drop_table("password_reset_tokens")
