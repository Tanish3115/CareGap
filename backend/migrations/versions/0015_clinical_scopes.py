"""Snapshot resource-scoped clinical requests/grants without expanding old consent."""

from alembic import op
import sqlalchemy as sa
import json

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None
GROUPS = [
    "allergies",
    "care_plans",
    "consultations",
    "diagnoses",
    "follow_ups",
    "interventions",
    "labs",
    "medications",
    "source_reviews",
]


def upgrade():
    for name in ("access_requests", "consent_grants"):
        op.add_column(name, sa.Column("clinical_resources", sa.JSON(), nullable=True))
        table = sa.table(
            name,
            sa.column("clinical_resources", sa.JSON()),
            sa.column("include_clinical_records", sa.Boolean()),
        )
        op.get_bind().execute(
            table.update().where(table.c.include_clinical_records.is_(True)).values(clinical_resources=GROUPS)
        )


def downgrade():
    # A downgrade must never silently broaden a restricted grant to legacy all-clinical.
    for name in ("access_requests", "consent_grants"):
        rows = (
            op.get_bind()
            .execute(
                sa.text(
                    f"SELECT id,clinical_resources FROM {name} WHERE include_clinical_records = "
                    + ("1" if op.get_bind().dialect.name == "sqlite" else "true")
                )
            )
            .all()
        )
        for identifier, resources in rows:
            if isinstance(resources, str):
                try:
                    resources = json.loads(resources)
                except ValueError:
                    resources = None
            full = (
                isinstance(resources, list)
                and all(isinstance(value, str) for value in resources)
                and set(resources) == set(GROUPS)
            )
            if not full:
                op.get_bind().execute(
                    sa.text(
                        f"UPDATE {name} SET include_clinical_records = :disabled,allow_clinical_write = :disabled WHERE id = :identifier"
                    ),
                    dict(disabled=False, identifier=identifier),
                )
        op.drop_column(name, "clinical_resources")
