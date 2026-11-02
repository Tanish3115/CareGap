from contextlib import contextmanager
from datetime import timedelta
import pytest
from app.core.time import utc_now
from app.file_cleanup import run_one
from app.models.document import MedicalDocument
from app.models.file_deletion import FileDeletion
from app.models.processing import DocumentProcessingJob
from app.models.medication_use import MedicationUse
from app.models.health_record import HealthRecord, HealthRevision
from app.services.storage_service import storage_service
from tests.helpers import pdf_bytes
from tests.test_hardening import admin_token as admin_token, headers
from tests.test_health_records import payload
from tests.test_medication_use import report


def upload(client, token):
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers(token),
        files={"file": ("synthetic.pdf", pdf_bytes("Synthetic deletion source"), "application/pdf")},
        data={"title": "Synthetic deletion document"},
    )
    assert response.status_code == 201
    return response.json()["document"]


def preview(client, token, document):
    return client.get(f"/api/v1/documents/{document['id']}/deletion-preview", headers=headers(token))


def delete_doc(client, token, document, value):
    return client.delete(f"/api/v1/documents/{document['id']}?expected_token={value}", headers=headers(token))


def cleanup(db):
    @contextmanager
    def factory():
        yield db

    return run_one(factory)


def test_document_deletion_is_private_transactional_and_cleanup_is_idempotent(
    client, patient_token, second_patient_token, doctor_token, admin_token, db_session
):
    document = upload(client, patient_token)
    root = db_session.get(MedicalDocument, document["id"])
    path = storage_service.resolve(root.file_path)
    state = preview(client, patient_token, document).json()
    assert state["allowed"] and "storage_key" not in state
    for token in [second_patient_token, doctor_token, admin_token]:
        assert preview(client, token, document).status_code == 403
        assert delete_doc(client, token, document, state["token"]).status_code == 403
    assert delete_doc(client, patient_token, document, "0" * 64).status_code == 409
    assert path.exists()
    assert delete_doc(client, patient_token, document, state["token"]).status_code == 202
    assert (
        client.get(f"/api/v1/documents/{document['id']}/download", headers=headers(patient_token)).status_code
        == 404
    )
    assert path.exists()  # No file destruction before the durable database transaction.
    receipt = client.get("/api/v1/patient-file-deletions", headers=headers(patient_token)).json()[0]
    assert receipt["status"] == "pending" and set(receipt) == {
        "document_id",
        "status",
        "attempts",
        "retry_required",
        "created_at",
    }
    assert client.get("/api/v1/patient-file-deletions", headers=headers(second_patient_token)).json() == []
    assert client.get("/api/v1/patient-file-deletions", headers=headers(doctor_token)).status_code == 403
    job = db_session.query(FileDeletion).one()
    assert job.status == "pending"
    assert cleanup(db_session)
    db_session.refresh(job)
    assert not path.exists() and job.status == "done" and job.storage_key == ""
    assert cleanup(db_session) is False


def test_cleanup_failure_retries_and_checks_checksum(client, patient_token, db_session):
    document = upload(client, patient_token)
    root = db_session.get(MedicalDocument, document["id"])
    path = storage_service.resolve(root.file_path)
    original = path.read_bytes()
    assert (
        delete_doc(
            client, patient_token, document, preview(client, patient_token, document).json()["token"]
        ).status_code
        == 202
    )
    path.write_bytes(b"Synthetic replaced object must not be deleted")
    assert cleanup(db_session)
    job = db_session.query(FileDeletion).one()
    assert job.status == "pending" and job.attempts == 1 and path.exists()
    path.write_bytes(original)
    job.next_attempt_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    assert cleanup(db_session)
    assert not path.exists()


def test_cleanup_missing_file_and_backend_routing(client, patient_token, db_session, monkeypatch):
    document = upload(client, patient_token)
    root = db_session.get(MedicalDocument, document["id"])
    root.storage_backend = "s3"
    db_session.commit()
    key = root.file_path
    assert (
        delete_doc(
            client, patient_token, document, preview(client, patient_token, document).json()["token"]
        ).status_code
        == 202
    )
    calls = []
    monkeypatch.setattr(storage_service, "delete_file", lambda key, backend: calls.append((key, backend)))
    assert cleanup(db_session) and calls == [(key, "s3")]


def test_active_processing_and_new_reviews_block_stale_document_deletion(client, patient_token, db_session):
    document = upload(client, patient_token)
    state = preview(client, patient_token, document).json()
    root = db_session.get(MedicalDocument, document["id"])
    root.review_version += 1
    db_session.commit()
    assert delete_doc(client, patient_token, document, state["token"]).status_code == 409
    job = db_session.query(DocumentProcessingJob).filter_by(document_id=root.id).one()
    job.status, job.lease_token, job.lease_until = (
        "processing",
        "synthetic-lease",
        utc_now() + timedelta(seconds=300),
    )
    db_session.commit()
    assert not preview(client, patient_token, document).json()["allowed"]
    assert delete_doc(client, patient_token, document, state["token"]).status_code == 409
    assert db_session.query(FileDeletion).count() == 0


def test_confirmed_entries_delete_with_document_but_linked_reports_require_review(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    from tests.test_prescriptions import setup_source, generate, save_payload
    from tests.test_hardening import grant
    from app.models.prescription import MedicationEntry

    document, path = setup_source(client, patient_token, db_session)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    draft = generate(client, patient_token, path)
    assert client.post(path, headers=headers(doctor_token), json=save_payload(draft, True)).status_code == 201
    entry = db_session.query(MedicationEntry).filter_by(document_id=document["id"]).first()
    account = client.post(
        "/api/v1/clinical/medication-use",
        headers=headers(patient_token),
        json=report(patient_user.patient_profile.id, source_entry_id=entry.id),
    ).json()
    state = preview(client, patient_token, document).json()
    assert not state["allowed"]
    assert delete_doc(client, patient_token, document, state["token"]).status_code == 409
    assert (
        client.delete(
            f"/api/v1/clinical/medication-use/{account['id']}?expected_version=1&expected_review_version=0",
            headers=headers(patient_token),
        ).status_code
        == 204
    )
    state = preview(client, patient_token, document).json()
    assert state["allowed"] and delete_doc(client, patient_token, document, state["token"]).status_code == 202
    assert db_session.query(MedicationEntry).filter_by(document_id=document["id"]).count() == 0
    assert cleanup(db_session)


def test_pending_document_cleanup_blocks_account_erasure(
    client, patient_token, patient_user, admin_token, db_session
):
    from tests.test_privacy_erasure import setup_request
    from app.services.privacy_erasure import eligibility, ErasureError
    from app.models.user import User

    document = upload(client, patient_token)
    assert (
        delete_doc(
            client, patient_token, document, preview(client, patient_token, document).json()["token"]
        ).status_code
        == 202
    )
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    with pytest.raises(ErasureError, match="pending document file cleanup"):
        eligibility(db_session, request.id, admin.id, policy)
    assert cleanup(db_session)
    eligibility(db_session, request.id, admin.id, policy)


def test_linked_consultation_must_be_explicitly_deleted_first(client, patient_token, patient_user):
    document = upload(client, patient_token)
    response = client.post(
        "/api/v1/clinical/encounters",
        headers=headers(patient_token),
        json=dict(
            patient_id=patient_user.patient_profile.id,
            title="Synthetic dependent consultation",
            notes="Synthetic account",
            occurred_on="2026-01-01",
            source_document_ids=[document["id"]],
        ),
    )
    assert response.status_code == 201
    state = preview(client, patient_token, document).json()
    assert not state["allowed"]
    assert delete_doc(client, patient_token, document, state["token"]).status_code == 409
    encounter = response.json()
    assert (
        client.delete(
            f"/api/v1/clinical/encounters/{encounter['id']}?expected_version=1",
            headers=headers(patient_token),
        ).status_code
        == 204
    )
    state = preview(client, patient_token, document).json()
    assert state["allowed"] and delete_doc(client, patient_token, document, state["token"]).status_code == 202


@pytest.mark.parametrize(
    "kind,data",
    [
        ("diagnosis", {"condition": "Synthetic condition"}),
        ("allergy", {"substance": "Synthetic substance"}),
        ("lab", {"test_name": "Synthetic lab", "value": "Source text"}),
        ("appointment", {"due_on": "2026-01-01"}),
        ("referral", {"due_on": "2026-01-01"}),
        ("test", {"due_on": "2026-01-01"}),
    ],
)
def test_delete_health_record_preserves_original_upload(
    client, patient_token, second_patient_token, doctor_token, patient_user, kind, data
):
    document = upload(client, patient_token)
    response = client.post(
        "/api/v1/clinical/records",
        headers=headers(patient_token),
        json=payload(
            patient_user.patient_profile.id, dict(kind=kind, **data), source_document_ids=[document["id"]]
        ),
    )
    assert response.status_code == 201, response.text
    root = response.json()
    path = f"/api/v1/clinical/records/{root['id']}"
    for token in [second_patient_token, doctor_token]:
        assert client.delete(path + "?expected_version=1", headers=headers(token)).status_code == 403
    assert client.delete(path + "?expected_version=2", headers=headers(patient_token)).status_code == 409
    assert client.delete(path + "?expected_version=1", headers=headers(patient_token)).status_code == 204
    assert client.get(path + "/history", headers=headers(patient_token)).status_code == 404
    assert (
        client.get(f"/api/v1/documents/{document['id']}/download", headers=headers(patient_token)).status_code
        == 200
    )


def test_medication_deletion_checks_both_report_and_review_versions(
    client, patient_token, patient_user, second_patient_token, db_session
):
    response = client.post(
        "/api/v1/clinical/medication-use",
        headers=headers(patient_token),
        json=report(patient_user.patient_profile.id),
    )
    assert response.status_code == 201
    root = response.json()
    path = f"/api/v1/clinical/medication-use/{root['id']}?expected_version=1&expected_review_version=0"
    assert client.delete(path, headers=headers(second_patient_token)).status_code == 403
    item = db_session.get(MedicationUse, root["id"])
    item.review_version = 1
    db_session.commit()
    assert client.delete(path, headers=headers(patient_token)).status_code == 409
    assert (
        client.delete(
            path.replace("review_version=0", "review_version=1"), headers=headers(patient_token)
        ).status_code
        == 204
    )
    assert (
        client.get(
            f"/api/v1/clinical/medication-use/{root['id']}/history", headers=headers(patient_token)
        ).status_code
        == 404
    )


def test_follow_up_deletion_preserves_consultation(client, patient_token, patient_user):
    parent = client.post(
        "/api/v1/clinical/encounters",
        headers=headers(patient_token),
        json=dict(
            patient_id=patient_user.patient_profile.id,
            title="Synthetic parent",
            notes="Retained source account",
            occurred_on="2026-01-01",
        ),
    ).json()
    task = client.post(
        "/api/v1/clinical/follow-ups",
        headers=headers(patient_token),
        json=dict(encounter_id=parent["id"], title="Synthetic follow-up", due_on="2026-01-02"),
    ).json()
    path = f"/api/v1/clinical/follow-ups/{task['id']}"
    assert client.delete(path + "?expected_version=2", headers=headers(patient_token)).status_code == 409
    assert client.delete(path + "?expected_version=1", headers=headers(patient_token)).status_code == 204
    assert client.get(path + "/history", headers=headers(patient_token)).status_code == 404
    assert (
        client.get(f"/api/v1/clinical/encounters/{parent['id']}", headers=headers(patient_token)).status_code
        == 200
    )


def test_care_target_deletion_checks_historical_intervention_links(
    client, patient_token, patient_user, db_session
):
    created = client.post(
        "/api/v1/clinical/records",
        headers=headers(patient_token),
        json=payload(patient_user.patient_profile.id, dict(kind="appointment", due_on="2026-01-01")),
    ).json()
    root = HealthRecord(patient_id=patient_user.patient_profile.id, kind="intervention", version=1)
    db_session.add(root)
    db_session.flush()
    db_session.add(
        HealthRevision(
            record_id=root.id,
            version=1,
            title="Synthetic intervention",
            occurred_on=utc_now().date(),
            data={"target_id": created["id"]},
            recorded_by=patient_user.id,
            provenance="clinician_recorded",
            reason="Synthetic link guard",
        )
    )
    db_session.commit()
    assert (
        client.delete(
            f"/api/v1/clinical/records/{created['id']}?expected_version=1", headers=headers(patient_token)
        ).status_code
        == 409
    )


def test_document_transaction_failure_does_not_destroy_file(client, patient_token, db_session, monkeypatch):
    document = upload(client, patient_token)
    path = storage_service.resolve(db_session.get(MedicalDocument, document["id"]).file_path)
    state = preview(client, patient_token, document).json()
    from app.api.deletions import audit_service

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(audit_service, "log_event", fail)
    assert delete_doc(client, patient_token, document, state["token"]).status_code == 500
    db_session.rollback()
    assert path.exists() and db_session.get(MedicalDocument, document["id"])
    assert db_session.query(FileDeletion).count() == 0
