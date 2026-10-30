from app.core.time import utc_now
import io
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from app.config import Settings, settings
from app.models.user import User
from app.models.consent import ConsentGrant
from app.models.document import MedicalDocument
from app.models.audit import AuditLog
from app.services.session_service import issue_session
from app.services.storage_service import storage_service
from app.core.security import create_access_token, decode_access_token, hash_password
from tests.helpers import pdf_bytes
from PIL import Image


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def upload(client, token, **data):
    return client.post("/api/v1/documents/upload", headers=headers(token),
                       files={"file": ("synthetic.pdf", pdf_bytes(), "application/pdf")},
                       data={"title": "Synthetic record", "document_type": "prescription", **data})


@pytest.fixture
def admin_token(db_session):
    user = User(email="admin@example.test", full_name="Synthetic Administrator", role="admin", hashed_password=hash_password("SyntheticAdmin123!"))
    db_session.add(user)
    db_session.flush()
    token = issue_session(db_session, user)
    db_session.commit()
    return token


def grant(db, patient, doctor, **overrides):
    values = dict(patient_id=patient.patient_profile.id, doctor_id=doctor.doctor_profile.id,
                  scope="all", purpose="Synthetic test review", valid_from=utc_now() - timedelta(minutes=1),
                  valid_until=utc_now() + timedelta(hours=1), is_revoked=False)
    values.update(overrides)
    item = ConsentGrant(**values)
    db.add(item)
    db.commit()
    return item


def test_public_admin_registration_rejected(client):
    response = client.post("/api/v1/auth/register", json={"email": "attacker@example.test", "full_name": "Test Admin", "password": "StrongPassword123!", "role": "admin"})
    assert response.status_code == 422


def test_admin_has_no_clinical_access(client, patient_token, admin_token, patient_user):
    document = upload(client, patient_token).json()["document"]
    for url in ["/api/v1/documents", f"/api/v1/documents?patient_id={patient_user.patient_profile.id}",
                f"/api/v1/documents/{document['id']}", f"/api/v1/documents/{document['id']}/download", "/api/v1/patients/me"]:
        assert client.get(url, headers=headers(admin_token)).status_code == 403
    assert upload(client, admin_token, patient_id=patient_user.patient_profile.id).status_code == 403


def test_doctor_upload_requires_explicit_permission(client, doctor_token, patient_user, doctor_user, db_session):
    target = patient_user.patient_profile.id
    assert upload(client, doctor_token, patient_id=target).status_code == 403
    item = grant(db_session, patient_user, doctor_user)
    assert upload(client, doctor_token, patient_id=target).status_code == 403
    item.allow_upload = True
    db_session.commit()
    assert upload(client, doctor_token, patient_id=target).status_code == 201


@pytest.mark.parametrize("state", ["pending", "rejected"])
def test_unverified_doctor_denied_even_with_grant(client, patient_token, doctor_token, patient_user, doctor_user, db_session, state):
    doc = upload(client, patient_token).json()["document"]
    grant(db_session, patient_user, doctor_user, allow_upload=True)
    doctor_user.doctor_profile.verification_status = state
    db_session.commit()
    for path in [f"/api/v1/documents/{doc['id']}", f"/api/v1/documents?patient_id={patient_user.patient_profile.id}"]:
        assert client.get(path, headers=headers(doctor_token)).status_code == 403
    assert upload(client, doctor_token, patient_id=patient_user.patient_profile.id).status_code == 403


@pytest.mark.parametrize("changes", [
    {"scope": "unknown"}, {"valid_until": utc_now() - timedelta(seconds=1)},
    {"valid_from": utc_now() + timedelta(hours=1)}, {"is_revoked": True},
])
def test_invalid_or_ineffective_grants_fail_closed(client, patient_token, doctor_token, patient_user, doctor_user, db_session, changes):
    doc = upload(client, patient_token).json()["document"]
    grant(db_session, patient_user, doctor_user, **changes)
    assert client.get(f"/api/v1/documents/{doc['id']}/download", headers=headers(doctor_token)).status_code == 403
    assert client.get(f"/api/v1/documents?patient_id={patient_user.patient_profile.id}", headers=headers(doctor_token)).status_code == 403


def test_multiple_scopes_are_combined(client, patient_token, doctor_token, patient_user, doctor_user, db_session):
    prescription = upload(client, patient_token).json()["document"]
    lab = upload(client, patient_token, document_type="lab_report").json()["document"]
    other = upload(client, patient_token, document_type="other").json()["document"]
    grant(db_session, patient_user, doctor_user, scope="labs_only")
    grant(db_session, patient_user, doctor_user, scope="prescriptions_only")
    response = client.get(f"/api/v1/documents?patient_id={patient_user.patient_profile.id}", headers=headers(doctor_token))
    assert {d["id"] for d in response.json()} == {prescription["id"], lab["id"]}
    assert client.get(f"/api/v1/documents/{other['id']}", headers=headers(doctor_token)).status_code == 403


@pytest.mark.parametrize("filename,mime,content", [
    ("empty.pdf", "application/pdf", b""), ("spoof.pdf", "application/pdf", b"not a PDF"),
    ("bad.png", "image/png", b"not a PNG"), ("mismatch.pdf", "image/png", pdf_bytes()),
    ("broken.pdf", "application/pdf", b"%PDF-1.4 corrupted"),
])
def test_invalid_content_rejected_without_persistence(client, patient_token, db_session, filename, mime, content):
    response = client.post("/api/v1/documents/upload", headers=headers(patient_token),
                           files={"file": (filename, content, mime)}, data={"title": "Synthetic"})
    assert response.status_code == 400
    assert db_session.query(MedicalDocument).count() == 0
    assert not list(storage_service.base_dir.rglob("*.pdf"))
    assert not list(storage_service.base_dir.rglob("*.png"))


def test_large_file_rejected(client, patient_token, monkeypatch):
    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 10)
    assert upload(client, patient_token).status_code == 400


@pytest.mark.parametrize("data", [{"clinical_date": "bad-date"}, {"document_type": "invented"}, {"title": " "}, {"patient_id": "../escape"}])
def test_invalid_metadata_rejected(client, patient_token, data):
    assert upload(client, patient_token, **data).status_code == 422


def test_patient_cannot_choose_another_owner(client, patient_token, second_patient_user):
    assert upload(client, patient_token, patient_id=second_patient_user.patient_profile.id).status_code == 403


def test_download_detects_tampering(client, patient_token, db_session):
    doc = upload(client, patient_token).json()["document"]
    entity = db_session.get(MedicalDocument, doc["id"])
    storage_service.resolve(entity.file_path).write_bytes(b"altered")
    response = client.get(f"/api/v1/documents/{doc['id']}/download", headers=headers(patient_token))
    assert response.status_code == 400
    assert "integrity" in response.json()["detail"].lower()


def test_storage_prefix_sibling_rejected(tmp_path):
    with pytest.raises(Exception) as error:
        storage_service.resolve(f"../{tmp_path.name}-sibling/file.pdf")
    assert getattr(error.value, "status_code", None) == 400


def test_cookie_logout_revokes_bearer_and_cookie(client, patient_user):
    login = client.post("/api/v1/auth/login", json={"email": patient_user.email, "password": "PatientSecure123!"})
    assert "HttpOnly" in login.headers["set-cookie"]
    token = login.json()["access_token"]
    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers(token)).status_code == 401


def test_cross_site_cookie_write_rejected(client, patient_user):
    client.post("/api/v1/auth/login", json={"email": patient_user.email, "password": "PatientSecure123!"})
    assert client.post("/api/v1/auth/logout", headers={"Origin": "https://untrusted.example"}).status_code == 403


def test_expired_token_and_missing_session_denied(client, patient_user):
    expired = create_access_token({"sub": patient_user.id, "jti": str(uuid4())}, expires_delta=timedelta(minutes=-2))
    assert decode_access_token(expired) is None
    assert client.get("/api/v1/auth/me", headers=headers(expired)).status_code == 401
    forged = create_access_token({"sub": patient_user.id, "jti": str(uuid4())})
    assert client.get("/api/v1/auth/me", headers=headers(forged)).status_code == 401


def test_default_secret_rejected():
    with pytest.raises(ValueError):
        Settings(SECRET_KEY="dev-insecure-secret-key-change-in-production")


@pytest.mark.parametrize("extension,format,mime", [("png", "PNG", "image/png"), ("jpg", "JPEG", "image/jpeg")])
def test_valid_image_round_trip(client, patient_token, extension, format, mime):
    content = io.BytesIO()
    Image.new("RGB", (8, 8), color="white").save(content, format=format)
    response = client.post("/api/v1/documents/upload", headers=headers(patient_token),
        files={"file": (f"synthetic.{extension}", content.getvalue(), mime)}, data={"title": "Synthetic image"})
    assert response.status_code == 201
    document = response.json()["document"]
    downloaded = client.get(f"/api/v1/documents/{document['id']}/download", headers=headers(patient_token))
    assert downloaded.content == content.getvalue()
    assert downloaded.headers["content-type"] == mime


def test_failed_upload_transaction_removes_file(client, patient_token, db_session, monkeypatch):
    from app.services.audit_service import audit_service
    def unavailable_audit(*args, **kwargs):
        raise RuntimeError("Synthetic transaction failure")
    monkeypatch.setattr(audit_service, "log_event", unavailable_audit)
    with pytest.raises(RuntimeError, match="Synthetic transaction failure"):
        upload(client, patient_token)
    assert db_session.query(MedicalDocument).count() == 0
    assert not list(storage_service.base_dir.rglob("*.pdf"))


def test_active_grant_stat_excludes_ineffective_grants(client, patient_token, patient_user, doctor_user, db_session):
    grant(db_session, patient_user, doctor_user)
    grant(db_session, patient_user, doctor_user, is_revoked=True)
    grant(db_session, patient_user, doctor_user, valid_until=utc_now() - timedelta(seconds=1))
    grant(db_session, patient_user, doctor_user, scope="unknown")
    stats = client.get("/api/v1/patients/summary/stats", headers=headers(patient_token)).json()
    assert stats["active_doctor_grants"] == 1
    assert stats["pending_care_gaps"] is None


def test_registration_saves_birth_date_and_profile_can_clear_fields(client):
    response = client.post("/api/v1/auth/register", json={"email": "synthetic-birthday@example.com", "password": "SyntheticBirthday123!", "full_name": "Synthetic Birthday", "date_of_birth": "2000-01-02", "emergency_contact": "Synthetic contact"})
    assert response.status_code == 201
    client.post("/api/v1/auth/login", json={"email": "synthetic-birthday@example.com", "password": "SyntheticBirthday123!"})
    assert client.get("/api/v1/patients/me").json()["date_of_birth"] == "2000-01-02"
    changed = client.put("/api/v1/patients/me", json={"emergency_contact": None})
    assert changed.status_code == 200
    assert changed.json()["emergency_contact"] is None
    assert changed.json()["date_of_birth"] == "2000-01-02"


def test_login_rate_limit_enforced(client, monkeypatch):
    from app.core.limiter import limiter
    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()
    responses = [client.post("/api/v1/auth/login", json={"email": "synthetic-missing@example.com", "password": "SyntheticInvalid123!"}) for _ in range(11)]
    assert [r.status_code for r in responses[:10]] == [401] * 10
    assert responses[10].status_code == 429
    limiter.reset()


def test_oversized_request_rejected_before_file_ingestion(client, patient_token):
    response = client.post("/api/v1/documents/upload", headers={**headers(patient_token), "Content-Length": "100000000"}, content=b"small synthetic body")
    assert response.status_code == 413
    assert not list(storage_service.base_dir.rglob("*.pdf"))
