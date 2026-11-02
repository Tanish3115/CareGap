import io
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from sqlalchemy.orm import sessionmaker

from app.core.time import utc_now
from app.models.document import MedicalDocument
from app.models.processing import DocumentProcessingJob
from app.services.document_processing import claim_job, finish_job
from app.services.storage_service import storage_service
from app.worker import run_one
from tests.test_hardening import admin_token as admin_token, headers, upload, grant


def pdf_with_text():
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 10 Td (Synthetic source only) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def run_worker(db_session, monkeypatch):
    monkeypatch.setenv("STORAGE_DIR", str(storage_service.base_dir))
    assert run_one(session_factory=sessionmaker(bind=db_session.bind))
    db_session.expire_all()


def test_real_pdf_processing_is_unverified_and_keeps_original(client, patient_token, db_session, monkeypatch):
    source_pdf = pdf_with_text()
    response = client.post(
        "/api/v1/documents/upload",
        headers=headers(patient_token),
        files={"file": ("source.pdf", source_pdf, "application/pdf")},
        data={"title": "Synthetic source text", "document_type": "other"},
    )
    assert response.status_code == 201
    doc = response.json()["document"]
    job = db_session.query(DocumentProcessingJob).one()
    assert job.status == "queued" and job.attempts == 0
    run_worker(db_session, monkeypatch)
    result = client.get(f"/api/v1/documents/{doc['id']}/processing", headers=headers(patient_token))
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "succeeded" and body["attempts"] == 1
    assert "Synthetic source only" in body["result"]["text"]
    assert body["result"]["verification_status"] == "unverified"
    assert body["result"]["source_sha256"] == doc["sha256_hash"]
    assert body["result"]["needs_ocr"] is False
    assert db_session.get(MedicalDocument, doc["id"]).status == "uploaded"
    assert (
        client.get(f"/api/v1/documents/{doc['id']}/download", headers=headers(patient_token)).content
        == source_pdf
    )
    assert (
        client.post(
            f"/api/v1/documents/{doc['id']}/processing/retry", headers=headers(patient_token)
        ).status_code
        == 409
    )


@pytest.mark.parametrize("kind", ["blank_pdf", "image"])
def test_scans_require_ocr_without_invented_text(client, patient_token, db_session, monkeypatch, kind):
    if kind == "blank_pdf":
        document = upload(client, patient_token).json()["document"]
    else:
        image = Image.new("RGB", (32, 32), color="white")
        content = io.BytesIO()
        image.save(content, format="PNG")
        document = client.post(
            "/api/v1/documents/upload",
            headers=headers(patient_token),
            files={"file": ("synthetic.png", content.getvalue(), "image/png")},
            data={"title": "Synthetic scan"},
        ).json()["document"]
    run_worker(db_session, monkeypatch)
    body = client.get(f"/api/v1/documents/{document['id']}/processing", headers=headers(patient_token)).json()
    assert body["status"] == "succeeded" and body["result"]["text"] == ""
    assert body["result"]["needs_ocr"] is True and body["result"]["verification_status"] == "unverified"


def test_failed_integrity_check_is_visible_and_can_be_retried(client, patient_token, db_session, monkeypatch):
    document = upload(client, patient_token).json()["document"]
    doc = db_session.get(MedicalDocument, document["id"])
    path = storage_service.resolve(doc.file_path)
    original = path.read_bytes()
    path.write_bytes(b"Synthetic corrupted content")
    run_worker(db_session, monkeypatch)
    url = f"/api/v1/documents/{doc.id}/processing"
    failed = client.get(url, headers=headers(patient_token)).json()
    assert failed["status"] == "failed" and failed["result"] is None and failed["can_retry"] is True
    assert failed["error_code"] == "processing_failed"
    path.write_bytes(original)
    assert client.post(url + "/retry", headers=headers(patient_token)).status_code == 202
    assert client.post(url + "/retry", headers=headers(patient_token)).status_code == 409
    run_worker(db_session, monkeypatch)
    final = client.get(url, headers=headers(patient_token)).json()
    assert final["status"] == "succeeded" and final["attempts"] == 2


def test_expired_leases_recover_and_old_workers_cannot_overwrite(db_session, client, patient_token):
    upload(client, patient_token)
    job_id, first_token = claim_job(db_session)
    job = db_session.get(DocumentProcessingJob, job_id, populate_existing=True)
    job.lease_until = utc_now() - timedelta(seconds=1)
    db_session.commit()
    assert claim_job(db_session)[0] == job_id
    job = db_session.get(DocumentProcessingJob, job_id, populate_existing=True)
    assert job.attempts == 2 and job.lease_token != first_token
    assert finish_job(db_session, job_id, first_token, error_code="timeout") is False
    assert finish_job(db_session, job_id, job.lease_token, error_code="timeout") is True
    assert db_session.get(DocumentProcessingJob, job_id, populate_existing=True).status == "failed"


def test_retry_limit_and_worker_crash_exhaustion(client, patient_token, db_session):
    document = upload(client, patient_token).json()["document"]
    for attempt in range(1, 4):
        job_id, token = claim_job(db_session)
        assert finish_job(db_session, job_id, token, error_code="timeout")
        response = client.post(
            f"/api/v1/documents/{document['id']}/processing/retry", headers=headers(patient_token)
        )
        assert response.status_code == (202 if attempt < 3 else 409)
    assert (
        client.get(f"/api/v1/documents/{document['id']}/processing", headers=headers(patient_token)).json()[
            "can_retry"
        ]
        is False
    )
    # A last-attempt crash also becomes a visible terminal failure on recovery.
    job = db_session.get(DocumentProcessingJob, job_id, populate_existing=True)
    job.status, job.lease_token, job.lease_until = "processing", token, utc_now() - timedelta(seconds=1)
    db_session.commit()
    assert claim_job(db_session) is None
    assert (
        db_session.get(DocumentProcessingJob, job_id, populate_existing=True).error_code == "lease_exhausted"
    )


def test_processing_results_follow_document_consent_and_only_owner_retries(
    client,
    patient_token,
    second_patient_token,
    doctor_token,
    admin_token,
    patient_user,
    doctor_user,
    db_session,
):
    document = upload(client, patient_token).json()["document"]
    url = f"/api/v1/documents/{document['id']}/processing"
    for token in (second_patient_token, doctor_token, admin_token):
        assert client.get(url, headers=headers(token)).status_code == 403
        assert client.post(url + "/retry", headers=headers(token)).status_code == 403
    active = grant(
        db_session, patient_user, doctor_user, scope="prescriptions_only", document_ids=[document["id"]]
    )
    assert client.get(url, headers=headers(doctor_token)).status_code == 200
    assert client.post(url + "/retry", headers=headers(doctor_token)).status_code == 403
    active.is_revoked = True
    db_session.commit()
    assert client.get(url, headers=headers(doctor_token)).status_code == 403


def test_legacy_document_processing_is_explicit_and_enqueued_once(client, patient_token, db_session):
    document = upload(client, patient_token).json()["document"]
    db_session.query(DocumentProcessingJob).delete()
    db_session.commit()
    url = f"/api/v1/documents/{document['id']}/processing"
    assert client.get(url, headers=headers(patient_token)).json()["status"] == "not_queued"
    assert client.post(url + "/retry", headers=headers(patient_token)).status_code == 202
    assert client.post(url + "/retry", headers=headers(patient_token)).status_code == 409
    assert db_session.query(DocumentProcessingJob).count() == 1


def test_concurrent_workers_claim_a_job_only_once(client, patient_token, db_session):
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("Separate transaction concurrency is exercised on PostgreSQL")
    upload(client, patient_token)
    factory = sessionmaker(bind=db_session.bind)
    gate = Barrier(2)

    def worker_claim():
        with factory() as session:
            gate.wait(timeout=10)
            return claim_job(session)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker_claim) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sum(result is not None for result in results) == 1
    db_session.expire_all()
    assert db_session.query(DocumentProcessingJob).one().attempts == 1
