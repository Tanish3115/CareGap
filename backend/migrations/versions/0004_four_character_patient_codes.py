"""Use one uppercase letter and three digits for patient sharing IDs."""
import re
import secrets
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

FORMAT_CHECK = (
    "length(patient_code) = 4 AND substr(patient_code, 1, 1) BETWEEN 'A' AND 'Z' "
    "AND substr(patient_code, 2, 1) BETWEEN '0' AND '9' "
    "AND substr(patient_code, 3, 1) BETWEEN '0' AND '9' "
    "AND substr(patient_code, 4, 1) BETWEEN '0' AND '9'"
)


def upgrade():
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, patient_code FROM patients ORDER BY id")).all()
    if len(rows) > 26_000:
        raise RuntimeError("One letter and three digits support at most 26,000 patients; no IDs were changed.")
    used = {code for _, code in rows if re.fullmatch(r"[A-Z][0-9]{3}", code)}
    remaining = [f"{chr(ord('A') + index // 1000)}{index % 1000:03d}" for index in range(26_000)]
    available = [code for code in remaining if code not in used]
    replacements = [(patient_id, code) for patient_id, code in rows if code not in used]
    selected = secrets.SystemRandom().sample(available, len(replacements))
    for (patient_id, _), code in zip(replacements, selected):
        connection.execute(sa.text("UPDATE patients SET patient_code = :code WHERE id = :id"),
                           {"id": patient_id, "code": code})
    with op.batch_alter_table("patients") as batch:
        batch.alter_column("patient_code", existing_type=sa.String(11), type_=sa.String(4), nullable=False)
        batch.create_check_constraint("ck_patients_patient_code_format", FORMAT_CHECK)


def downgrade():
    with op.batch_alter_table("patients") as batch:
        batch.drop_constraint("ck_patients_patient_code_format", type_="check")
        batch.alter_column("patient_code", existing_type=sa.String(4), type_=sa.String(11), nullable=False)
    connection = op.get_bind()
    used = set()
    for patient_id in connection.execute(sa.text("SELECT id FROM patients")).scalars().all():
        while True:
            code = f"CG-{secrets.randbelow(90_000_000) + 10_000_000}"
            if code not in used:
                used.add(code)
                break
        connection.execute(sa.text("UPDATE patients SET patient_code = :code WHERE id = :id"),
                           {"id": patient_id, "code": code})
