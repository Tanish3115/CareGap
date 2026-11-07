"""Build an isolated disposable demo with random credentials; never seeds app data."""

import json
import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

root = Path(__file__).resolve().parents[1]
folder = root / ".tools/demo" / uuid4().hex
folder.mkdir(parents=True, exist_ok=False)
vault = folder / "vault"
vault.mkdir()
secret = secrets.token_urlsafe(48)
os.environ.update(
    DATABASE_URL=f"sqlite:///{(folder / 'demo.db').as_posix()}",
    SECRET_KEY=secret,
    ENVIRONMENT="test",
    STORAGE_DIR=str(vault),
)
sys.path.insert(0, str(root / "backend"))
from alembic import command
from alembic.config import Config

command.upgrade(Config(str(root / "backend/alembic.ini")), "head")
from sqlalchemy.orm import Session
from app.database import engine
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.consent import ConsentGrant
from app.models.health_record import HealthRecord, HealthRevision, HealthSource
from app.models.document import MedicalDocument
from app.models.processing import DocumentProcessingJob
from app.core.security import hash_password
from app.core.time import utc_now
import hashlib


def pdf():
    stream = b"BT /F1 10 Tf 30 740 Td (SYNTHETIC CareGap software fixture. No real patient or medication.) Tj 0 -20 Td (Medicine: SYNTHETIC-A | Dose: 1 synthetic unit) Tj 0 -20 Td (Synthetic condition. Allergy: SYNTHETIC-A. Synthetic referral.) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    result = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    position = len(result)
    result += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(
        f"{offset:010} 00000 n \n".encode() for offset in offsets
    )
    return result + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{position}\n%%EOF\n".encode()


credentials = {}
with Session(engine) as db:
    users = {}
    for role, name in [
        ("patient", "Synthetic Demo Patient"),
        ("doctor", "Synthetic Demo Clinician"),
        ("admin", "Synthetic Demo Administrator"),
    ]:
        password = secrets.token_urlsafe(24)
        user = User(
            email=f"synthetic-{role}@example.test",
            full_name=name,
            role=role,
            hashed_password=hash_password(password),
        )
        db.add(user)
        db.flush()
        users[role] = user
        credentials[role] = dict(email=user.email, password=password)
    patient = Patient(user_id=users["patient"].id, patient_code="D360")
    db.add(patient)
    db.flush()
    doctor = Doctor(
        user_id=users["doctor"].id,
        license_number=f"SYNTHETIC-{uuid4().hex}",
        specialization="Synthetic software testing",
        verification_status="verified",
    )
    db.add(doctor)
    db.flush()
    db.add(
        ConsentGrant(
            patient_id=patient.id,
            doctor_id=doctor.id,
            scope="all",
            purpose="Explicit synthetic demo sharing",
            include_clinical_records=True,
            allow_clinical_write=True,
            valid_until=utc_now() + timedelta(days=7),
        )
    )
    content = pdf()
    key = f"{patient.id}/{uuid4()}.pdf"
    path = vault / key
    path.parent.mkdir()
    path.write_bytes(content)
    source = MedicalDocument(
        patient_id=patient.id,
        uploader_id=users["patient"].id,
        title="Synthetic fixture source",
        document_type="prescription",
        file_path=key,
        file_name="synthetic.pdf",
        file_size=len(content),
        mime_type="application/pdf",
        sha256_hash=hashlib.sha256(content).hexdigest(),
        status="uploaded",
    )
    db.add(source)
    db.flush()
    db.add(DocumentProcessingJob(document_id=source.id))
    today = utc_now().date()
    for title, data in [
        (
            "Synthetic documented condition",
            dict(kind="diagnosis", condition="Synthetic condition", status="unknown"),
        ),
        (
            "Synthetic allergy account",
            dict(kind="allergy", substance="SYNTHETIC-A", reaction=None, status="unknown"),
        ),
        (
            "Synthetic overdue referral",
            dict(
                kind="referral",
                due_on=(today - timedelta(days=2)).isoformat(),
                status="pending",
                barriers=["transport"],
                outcome=None,
            ),
        ),
        (
            "Synthetic upcoming appointment",
            dict(
                kind="appointment",
                due_on=(today + timedelta(days=2)).isoformat(),
                status="pending",
                barriers=[],
                outcome=None,
            ),
        ),
    ]:
        record = HealthRecord(patient_id=patient.id, kind=data["kind"])
        db.add(record)
        db.flush()
        db.add(
            HealthRevision(
                record_id=record.id,
                version=1,
                title=title,
                occurred_on=today,
                data=data,
                recorded_by=users["patient"].id,
                provenance="patient_reported",
                reason="Isolated synthetic demonstration fixture",
                sources=[HealthSource(document_id=source.id)],
            )
        )
    db.commit()
(folder / "credentials.json").write_text(json.dumps(credentials, indent=2) + "\n", encoding="utf-8")
(folder / "demo.env").write_text(
    "\n".join(
        f"{key}={os.environ[key]}" for key in ("DATABASE_URL", "SECRET_KEY", "ENVIRONMENT", "STORAGE_DIR")
    )
    + "\n",
    encoding="utf-8",
)
print(
    json.dumps(
        dict(
            demo_directory=str(folder),
            credentials_file=str(folder / "credentials.json"),
            patient_code="D360",
            instructions="Use this demo.env in a separate development process. It does not change the running application or its users.",
        )
    )
)
