from app.models.document import MedicalDocument
from app.models.document_review import DocumentReviewRevision
from app.models.processing import DocumentProcessingJob
from app.schemas.processing import SourceTextResult
from app.services.document_processing import claim_job, finish_job
from app.services.storage_service import storage_service
from tests.test_hardening import admin_token as admin_token, headers, upload, grant


def processed(client, token, db):
    document = upload(client, token).json()["document"]
    job_id, lease = claim_job(db)
    result = SourceTextResult(
        kind="pdf_text",
        text="Synthetic source transcription",
        source_sha256=document["sha256_hash"],
        page_count=1,
        needs_ocr=False,
        truncated=False,
    )
    assert finish_job(db, job_id, lease, result=result.model_dump())
    return document


def payload(**overrides):
    values = dict(
        expected_version=0,
        expected_attempt=1,
        reviewed_text="Human-reviewed synthetic transcription",
        reason="Compared against the synthetic original source",
        source_checked=True,
    )
    values.update(overrides)
    return values


def test_review_versions_keep_generated_source_and_do_not_verify_clinical_data(
    client, patient_token, db_session
):
    doc = processed(client, patient_token, db_session)
    url = f"/api/v1/documents/{doc['id']}/review"
    assert client.get(url, headers=headers(patient_token)).json() is None
    created = client.post(url, headers=headers(patient_token), json=payload())
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["version"] == 1 and body["reviewer_kind"] == "patient_reviewed"
    assert (
        body["source_text"] == "Synthetic source transcription"
        and body["source_sha256"] == doc["sha256_hash"]
    )
    assert client.post(url, headers=headers(patient_token), json=payload()).status_code == 409
    changed = client.post(
        url,
        headers=headers(patient_token),
        json=payload(expected_version=1, reviewed_text="Second synthetic correction"),
    )
    assert changed.status_code == 201 and changed.json()["version"] == 2
    history = client.get(url + "/history", headers=headers(patient_token)).json()
    assert [row["version"] for row in history] == [2, 1]
    assert history[1]["reviewed_text"] == body["reviewed_text"]
    assert all(row["source_text"] == body["source_text"] for row in history)
    assert db_session.get(MedicalDocument, doc["id"]).status == "uploaded"


def test_review_requires_complete_matching_processing_and_source_confirmation(
    client, patient_token, db_session
):
    doc = upload(client, patient_token).json()["document"]
    url = f"/api/v1/documents/{doc['id']}/review"
    assert client.post(url, headers=headers(patient_token), json=payload()).status_code == 409
    job_id, token = claim_job(db_session)
    result = SourceTextResult(
        kind="pdf_text",
        text="Synthetic",
        source_sha256=doc["sha256_hash"],
        page_count=1,
        needs_ocr=False,
        truncated=False,
    )
    finish_job(db_session, job_id, token, result=result.model_dump())
    assert (
        client.post(url, headers=headers(patient_token), json=payload(source_checked=False)).status_code
        == 422
    )
    assert (
        client.post(url, headers=headers(patient_token), json=payload(expected_attempt=2)).status_code == 409
    )
    assert (
        client.post(
            url, headers=headers(patient_token), json=payload(patient_id="forged-patient")
        ).status_code
        == 422
    )
    assert (
        client.post(url, headers=headers(patient_token), json=payload(reviewed_text=" ")).status_code == 422
    )
    assert db_session.query(DocumentReviewRevision).count() == 0


def test_review_rejects_missing_or_changed_original_and_wrong_checksum(client, patient_token, db_session):
    doc = processed(client, patient_token, db_session)
    url = f"/api/v1/documents/{doc['id']}/review"
    entity = db_session.get(MedicalDocument, doc["id"])
    path = storage_service.resolve(entity.file_path)
    original = path.read_bytes()
    path.write_bytes(b"Synthetic tampered source")
    assert client.post(url, headers=headers(patient_token), json=payload()).status_code == 400
    path.unlink()
    assert client.post(url, headers=headers(patient_token), json=payload()).status_code == 400
    path.write_bytes(original)
    job = db_session.query(DocumentProcessingJob).one()
    job.result = {**job.result, "source_sha256": "0" * 64}
    db_session.commit()
    assert client.post(url, headers=headers(patient_token), json=payload()).status_code == 409
    assert db_session.query(DocumentReviewRevision).count() == 0


def test_manual_reviews_need_clinical_consent_in_addition_to_source_access(
    client,
    patient_token,
    second_patient_token,
    doctor_token,
    admin_token,
    patient_user,
    doctor_user,
    db_session,
):
    doc = processed(client, patient_token, db_session)
    url = f"/api/v1/documents/{doc['id']}/review"
    for token in (second_patient_token, doctor_token, admin_token):
        assert client.get(url, headers=headers(token)).status_code == 403
        assert client.post(url, headers=headers(token), json=payload()).status_code == 403
    grant(db_session, patient_user, doctor_user, scope="prescriptions_only", document_ids=[doc["id"]])
    assert (
        client.get(f"/api/v1/documents/{doc['id']}/processing", headers=headers(doctor_token)).status_code
        == 200
    )
    assert client.get(url, headers=headers(doctor_token)).status_code == 403
    clinical = grant(db_session, patient_user, doctor_user, include_clinical_records=True)
    assert client.get(url, headers=headers(doctor_token)).status_code == 200
    assert client.post(url, headers=headers(doctor_token), json=payload()).status_code == 403
    clinical.allow_clinical_write = True
    db_session.commit()
    created = client.post(url, headers=headers(doctor_token), json=payload())
    assert created.status_code == 201 and created.json()["reviewer_kind"] == "clinician_reviewed"
    clinical.is_revoked = True
    db_session.commit()
    assert client.get(url, headers=headers(doctor_token)).status_code == 403
    assert client.get(url + "/history", headers=headers(doctor_token)).status_code == 403
    assert (
        client.post(url, headers=headers(doctor_token), json=payload(expected_version=1)).status_code == 403
    )
    flags = client.get(f"/api/v1/documents/{doc['id']}/processing", headers=headers(doctor_token)).json()
    assert flags["can_view_review"] is False and flags["can_review"] is False


def test_updated_ocr_keeps_previous_reviews_and_rejects_reviewing_active_processing(
    client, patient_token, db_session
):
    doc = processed(client, patient_token, db_session)
    url = f"/api/v1/documents/{doc['id']}"
    assert client.post(url + "/review", headers=headers(patient_token), json=payload()).status_code == 201
    assert client.get(url + "/processing", headers=headers(patient_token)).json()["can_reprocess"] is True
    assert client.post(url + "/processing/retry", headers=headers(patient_token)).status_code == 202
    assert (
        client.post(
            url + "/review", headers=headers(patient_token), json=payload(expected_version=1)
        ).status_code
        == 409
    )
    job_id, lease = claim_job(db_session)
    upgraded = SourceTextResult(
        kind="pdf_text",
        text="Updated synthetic source text",
        source_sha256=doc["sha256_hash"],
        page_count=1,
        needs_ocr=False,
        truncated=False,
        processor_version="source-ocr-v2",
    )
    assert finish_job(db_session, job_id, lease, result=upgraded.model_dump())
    assert (
        client.get(url + "/review", headers=headers(patient_token)).json()["source_text"]
        == "Synthetic source transcription"
    )
    assert (
        client.post(
            url + "/review", headers=headers(patient_token), json=payload(expected_version=1)
        ).status_code
        == 409
    )
    response = client.post(
        url + "/review", headers=headers(patient_token), json=payload(expected_version=1, expected_attempt=2)
    )
    assert response.status_code == 201 and response.json()["source_text"] == upgraded.text
    history = client.get(url + "/review/history", headers=headers(patient_token)).json()
    assert [item["processing_attempt"] for item in history] == [2, 1]
