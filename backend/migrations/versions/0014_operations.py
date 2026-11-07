"""Verified organization-bound grants and operational privacy workflow."""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("evidence", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("status IN ('pending','verified','inactive')"),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("organization_id", "user_id"),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("role IN ('clinician','staff')"),
        sa.CheckConstraint("status IN ('active','inactive')"),
    )
    for col in ("organization_id", "user_id"):
        op.create_index(f"ix_organization_memberships_{col}", "organization_memberships", [col])
    op.create_table(
        "organization_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("change", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_organization_history_organization_id", "organization_history", ["organization_id"])
    op.create_table(
        "privacy_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("decision_reference", sa.String(500)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("version >= 1"),
        sa.CheckConstraint("kind IN ('export','correction','erasure')"),
        sa.CheckConstraint("status IN ('requested','under_review','closed')"),
    )
    op.create_index("ix_privacy_requests_user_id", "privacy_requests", ["user_id"])
    for table in ("access_requests", "consent_grants"):
        if op.get_bind().dialect.name == "sqlite":
            op.execute(
                f"ALTER TABLE {table} ADD COLUMN organization_id VARCHAR(36) REFERENCES organizations(id)"
            )
        else:
            op.add_column(
                table,
                sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True),
            )


def downgrade():
    for table in ("access_requests", "consent_grants"):
        op.drop_column(table, "organization_id")
    op.drop_table("privacy_requests")
    op.drop_table("organization_history")
    op.drop_table("organization_memberships")
    op.drop_table("organizations")
