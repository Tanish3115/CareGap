"""Exercise dump/restore on generated synthetic databases only; never restores over app data."""

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
values = dotenv_values(root / ".env")
base = URL.create(
    "postgresql+psycopg",
    username="caregap_user",
    password=values["POSTGRES_PASSWORD"],
    host="127.0.0.1",
    port=int(values.get("POSTGRES_PORT", 55432)),
    database="postgres",
)
names = ["caregap_restore_" + uuid4().hex for _ in range(2)]
assert all(re.fullmatch(r"caregap_restore_[a-f0-9]{32}", name) for name in names)
maintenance = create_engine(base, isolation_level="AUTOCOMMIT")
created = []
engines = []
try:
    for name in names:
        with maintenance.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        created.append(name)
    from app.config import settings

    settings.DATABASE_URL = base.set(database=names[0]).render_as_string(hide_password=False)
    from alembic import command
    from alembic.config import Config
    from app.database import Base
    import app.models  # noqa: F401 -- register models for the isolated restore comparison
    from sqlalchemy.orm import Session
    from app.models.user import User
    from app.models.patient import Patient
    from app.models.document import MedicalDocument
    from app.models.health_record import HealthRecord, HealthRevision
    from app.core.time import utc_now
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    command.upgrade(Config(str(root / "backend/alembic.ini")), "head")
    engine = create_engine(base.set(database=names[0]))
    engines.append(engine)
    sample = b"Synthetic backup integrity fixture; no real medical data."
    digest = hashlib.sha256(sample).hexdigest()
    with Session(engine) as db:
        user = User(
            email="restore-synthetic@example.test",
            full_name="Synthetic restore patient",
            hashed_password="synthetic-non-login-hash",
            role="patient",
        )
        db.add(user)
        db.flush()
        patient = Patient(user_id=user.id, patient_code="Z999")
        db.add(patient)
        db.flush()
        doc = MedicalDocument(
            patient_id=patient.id,
            uploader_id=user.id,
            title="Synthetic restore source",
            document_type="other",
            file_path=f"{patient.id}/{uuid4()}.pdf",
            file_name="synthetic.pdf",
            file_size=len(sample),
            mime_type="application/pdf",
            sha256_hash=digest,
            status="uploaded",
        )
        record = HealthRecord(patient_id=patient.id, kind="diagnosis")
        db.add_all([doc, record])
        db.flush()
        db.add(
            HealthRevision(
                record_id=record.id,
                version=1,
                title="Synthetic restore condition",
                occurred_on=utc_now().date(),
                data=dict(kind="diagnosis", condition="SYNTHETIC", status="unknown", notes=None),
                recorded_by=user.id,
                provenance="patient_reported",
                reason="Synthetic restore exercise",
            )
        )
        db.commit()
    dump = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_dump",
            "-U",
            "caregap_user",
            "-d",
            names[0],
            "-Fc",
        ],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "pg_restore",
            "-U",
            "caregap_user",
            "-d",
            names[1],
            "--exit-on-error",
        ],
        cwd=root,
        input=dump,
        capture_output=True,
        check=True,
    )
    restored = create_engine(base.set(database=names[1]))
    engines.append(restored)
    with restored.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM users")).scalar_one() == 1
        assert connection.execute(text("SELECT sha256_hash FROM medical_documents")).scalar_one() == digest
        assert connection.execute(text("SELECT count(*) FROM health_revisions")).scalar_one() == 1
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    workspace_tools = root / ".tools"
    workspace_tools.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="caregap-restore-", dir=workspace_tools) as directory:
        folder = Path(directory).resolve()
        assert folder.is_relative_to(workspace_tools.resolve())
        (folder / "original").write_bytes(sample)
        shutil.copyfile(folder / "original", folder / "restored")
        assert hashlib.sha256((folder / "restored").read_bytes()).hexdigest() == digest
    print(
        "Synthetic PostgreSQL dump/restore, schema comparison and file checksum preservation passed. Application data was not accessed."
    )
finally:
    for engine in engines:
        engine.dispose()
    for name in created:
        assert re.fullmatch(r"caregap_restore_[a-f0-9]{32}", name)
        with maintenance.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}"'))
    maintenance.dispose()
