import io
from datetime import datetime, timedelta
import pytest
from app.models.consent import ConsentGrant, ConsentScope
from app.models.audit import AuditLog, AuditAction


def test_cross_patient_unauthorized_access_denied(client, patient_token, second_patient_token, db_session):
    # Patient 1 uploads a private document
    file_content = b"Patient 1 confidential health record"
    upload_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        files={"file": ("p1_record.pdf", io.BytesIO(file_content), "application/pdf")},
        data={"title": "Patient 1 Private Record", "document_type": "prescription"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    # Patient 2 tries to access Patient 1's document metadata -> Must fail 403 Forbidden
    unauthorized_res = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {second_patient_token}"},
    )
    assert unauthorized_res.status_code == 403
    assert "not authorized" in unauthorized_res.json()["detail"].lower()

    # Patient 2 tries to download Patient 1's binary file -> Must fail 403 Forbidden
    unauthorized_dl = client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {second_patient_token}"},
    )
    assert unauthorized_dl.status_code == 403

    # Check audit log registered unauthorized access attempt
    audit = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == AuditAction.UNAUTHORIZED_ACCESS_ATTEMPT.value)
        .first()
    )
    assert audit is not None
    assert audit.resource_id == doc_id


def test_doctor_cannot_access_patient_record_without_consent(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    # Patient uploads document
    upload_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        files={"file": ("visit_summary.pdf", io.BytesIO(b"Visit Summary Content"), "application/pdf")},
        data={"title": "Confidential Consultation", "document_type": "discharge_summary"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]
    patient_id = patient_user.patient_profile.id

    # Doctor tries to retrieve patient's documents list -> Fails 403 Forbidden
    list_res = client.get(
        f"/api/v1/documents?patient_id={patient_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert list_res.status_code == 403
    assert "no active consent" in list_res.json()["detail"].lower()

    # Doctor tries to retrieve document directly -> Fails 403 Forbidden
    direct_res = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert direct_res.status_code == 403


def test_doctor_access_granted_with_active_consent(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    # Patient uploads document
    upload_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        files={"file": ("presc.pdf", io.BytesIO(b"Amoxicillin 500mg BID"), "application/pdf")},
        data={"title": "Prescription", "document_type": "prescription"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]
    patient_id = patient_user.patient_profile.id
    doctor_id = doctor_user.doctor_profile.id

    # Create active ConsentGrant
    grant = ConsentGrant(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scope=ConsentScope.ALL.value,
        purpose="Cardiology Consultation Follow-up",
        valid_from=datetime.utcnow() - timedelta(minutes=5),
        valid_until=datetime.utcnow() + timedelta(days=1),
        is_revoked=False,
    )
    db_session.add(grant)
    db_session.commit()

    # Doctor can now retrieve documents list
    list_res = client.get(
        f"/api/v1/documents?patient_id={patient_id}",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) >= 1
    assert any(d["id"] == doc_id for d in docs)

    # Doctor can download document
    dl_res = client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert dl_res.status_code == 200
    assert dl_res.content == b"Amoxicillin 500mg BID"


def test_revoked_consent_blocks_future_doctor_access(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    upload_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        files={"file": ("lab.pdf", io.BytesIO(b"Lab results"), "application/pdf")},
        data={"title": "Lipid Profile", "document_type": "lab_report"},
    )
    doc_id = upload_res.json()["document"]["id"]
    patient_id = patient_user.patient_profile.id
    doctor_id = doctor_user.doctor_profile.id

    # Create REVOKED ConsentGrant
    grant = ConsentGrant(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scope=ConsentScope.ALL.value,
        purpose="Consultation",
        valid_from=datetime.utcnow() - timedelta(days=1),
        valid_until=datetime.utcnow() + timedelta(days=1),
        is_revoked=True,
        revoked_at=datetime.utcnow(),
    )
    db_session.add(grant)
    db_session.commit()

    # Doctor tries to view document -> Denied 403 Forbidden
    dl_res = client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {doctor_token}"},
    )
    assert dl_res.status_code == 403

