"""Opt-in real private object-store tests; always use a unique synthetic test bucket."""

import os
import urllib.error
import urllib.request
from sqlalchemy.orm import sessionmaker
import pytest
from app.config import settings
from app.models.document import MedicalDocument
from app.services.storage_service import storage_service
from app.worker import run_one
from tests.test_hardening import headers, upload
from tests.helpers import pdf_bytes

pytestmark = pytest.mark.skipif(
    os.environ.get("CAREGAP_S3_INTEGRATION") != "1",
    reason="Run scripts/check_s3.py against isolated local MinIO",
)


def test_actual_private_upload_download_processing_and_anonymous_denial(
    client, patient_token, second_patient_token, db_session
):
    response = upload(client, patient_token)
    assert response.status_code == 201, response.text
    doc = response.json()["document"]
    entity = db_session.get(MedicalDocument, doc["id"])
    assert entity.storage_backend == "s3"
    assert (
        client.get(f"/api/v1/documents/{doc['id']}/download", headers=headers(patient_token)).content
        == pdf_bytes()
    )
    assert (
        client.get(
            f"/api/v1/documents/{doc['id']}/download", headers=headers(second_patient_token)
        ).status_code
        == 403
    )
    with pytest.raises(urllib.error.HTTPError) as denied:
        urllib.request.urlopen(
            f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{entity.file_path}", timeout=10
        )
    assert denied.value.code == 403
    assert run_one(session_factory=sessionmaker(bind=db_session.bind))
    body = client.get(f"/api/v1/documents/{doc['id']}/processing", headers=headers(patient_token)).json()
    assert body["status"] == "succeeded" and body["result"]["verification_status"] == "unverified"


def test_actual_object_tampering_is_rejected(client, patient_token, db_session):
    doc = upload(client, patient_token).json()["document"]
    entity = db_session.get(MedicalDocument, doc["id"])
    storage_service.s3.client.put_object(
        Bucket=settings.S3_BUCKET, Key=entity.file_path, Body=b"Synthetic tampered content"
    )
    response = client.get(f"/api/v1/documents/{doc['id']}/download", headers=headers(patient_token))
    assert response.status_code == 400 and "integrity" in response.json()["detail"]
