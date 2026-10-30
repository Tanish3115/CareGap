from tests.helpers import pdf_bytes
import io
import pytest


def test_upload_pdf_prescription_success(client, patient_token):
    file_content = pdf_bytes('%PDF-1.4 sample clinical prescription text for test')
    file_obj = io.BytesIO(file_content)

    response = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        files={"file": ("prescription_visit1.pdf", file_obj, "application/pdf")},
        data={
            "title": "Cardiology Consultation Prescription",
            "document_type": "prescription",
            "clinical_date": "2026-10-15",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Medical document securely stored and registered"
    doc = data["document"]
    assert doc["title"] == "Cardiology Consultation Prescription"
    assert doc["document_type"] == "prescription"
    assert doc["file_name"] == "prescription_visit1.pdf"
    assert doc["file_size"] == len(file_content)
    assert len(doc["sha256_hash"]) == 64  # valid SHA-256 string
    assert doc["status"] == "uploaded"


def test_upload_disallowed_extension_fails(client, patient_token):
    file_content = pdf_bytes('malicious binary payload')
    file_obj = io.BytesIO(file_content)

    response = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        files={"file": ("exploit.exe", file_obj, "application/octet-stream")},
        data={"title": "Malware file"},
    )
    assert response.status_code == 400
    assert "not permitted" in response.json()["detail"]


def test_list_and_download_patient_documents(client, patient_token):
    # 1. Upload a document
    file_content = pdf_bytes('Simulated Blood Test CBC Results: Normal')
    file_obj = io.BytesIO(file_content)

    upload_res = client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {patient_token}"},
        files={"file": ("cbc_report.pdf", file_obj, "application/pdf")},
        data={"title": "Complete Blood Count", "document_type": "lab_report"},
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["document"]["id"]

    # 2. List documents
    list_res = client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) >= 1
    assert any(d["id"] == doc_id for d in docs)

    # 3. Retrieve metadata
    meta_res = client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert meta_res.status_code == 200
    assert meta_res.json()["id"] == doc_id
    assert meta_res.json()["document_type"] == "lab_report"

    # 4. Download binary
    download_res = client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {patient_token}"},
    )
    assert download_res.status_code == 200
    assert download_res.content == file_content
    assert download_res.headers["content-type"] == "application/pdf"

