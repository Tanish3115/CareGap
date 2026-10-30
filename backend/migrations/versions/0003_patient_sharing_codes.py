"""Add simple patient sharing codes without changing existing UUID relationships."""
import secrets
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("patients", sa.Column("patient_code", sa.String(11), nullable=True))
    connection = op.get_bind()
    codes = set()
    for patient_id in connection.execute(sa.text("SELECT id FROM patients")).scalars().all():
        while True:
            code = f"CG-{secrets.randbelow(90_000_000) + 10_000_000}"
            if code not in codes:
                codes.add(code)
                break
        connection.execute(sa.text("UPDATE patients SET patient_code = :code WHERE id = :id"),
                           {"code": code, "id": patient_id})
    with op.batch_alter_table("patients") as batch:
        batch.alter_column("patient_code", existing_type=sa.String(11), nullable=False)
    op.create_index("ix_patients_patient_code", "patients", ["patient_code"], unique=True)


def downgrade():
    op.drop_index("ix_patients_patient_code", table_name="patients")
    with op.batch_alter_table("patients") as batch:
        batch.drop_column("patient_code")
