import json
import os
from datetime import date
from datetime import datetime, timezone
import pytest
from app.models.user import User
from app.models.patient import Patient
from app.models.operations import PrivacyRequest, Organization, OrganizationHistory
from app.models.consent import ConsentGrant
from app.models.processing import DocumentProcessingJob
from app.models.document import MedicalDocument
from app.models.audit import AuditLog
from app.models.session import AuthSession
from app.models.health_record import HealthRecord, HealthRevision, HealthSource
from app.services.storage_service import storage_service
from app.core.time import utc_now
from app.services.privacy_erasure import ErasureError, ErasurePolicy, build_plan, digest, execute_plan
from tests.test_hardening import admin_token as admin_token, grant, headers, upload
from tests.test_prescriptions import setup_source, generate, save_payload
from tests.test_clinical import create_encounter
from tests.test_health_records import payload, BASE
from tests.test_medication_use import create as create_use


def setup_request(db, user):
    user.is_active = False
    db.query(AuthSession).filter_by(user_id=user.id).update(dict(revoked_at=utc_now()))
    db.query(ConsentGrant).filter_by(patient_id=user.patient_profile.id).update(dict(is_revoked=True))
    request = PrivacyRequest(
        user_id=user.id, kind="erasure", status="under_review", decision_reference="SYNTHETIC-POLICY-v1"
    )
    db.add(request)
    db.commit()
    return request, ErasurePolicy(
        reference="SYNTHETIC-POLICY-v1",
        backup_procedure_reference="SYNTHETIC-BACKUP-v1",
        eligible_after=datetime(2020, 1, 1, tzinfo=timezone.utc),
        retain_pseudonymous_account=True,
    )


def test_erasure_plan_and_execution_remove_only_the_approved_patient_graph(
    client,
    patient_token,
    doctor_token,
    admin_token,
    patient_user,
    doctor_user,
    second_patient_user,
    db_session,
    tmp_path,
):
    target = patient_user.patient_profile.id
    doc, url = setup_source(client, patient_token, db_session)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    draft = generate(client, patient_token, url)
    assert client.post(url, headers=headers(doctor_token), json=save_payload(draft, True)).status_code == 201
    encounter = create_encounter(client, patient_token, target, source_document_ids=[doc["id"]]).json()
    client.post(
        "/api/v1/clinical/follow-ups",
        headers=headers(patient_token),
        json=dict(encounter_id=encounter["id"], title="Synthetic follow-up", due_on="2026-01-01"),
    )
    client.post(
        BASE,
        headers=headers(patient_token),
        json=payload(
            target, dict(kind="lab", test_name="PRIVATE synthetic lab"), source_document_ids=[doc["id"]]
        ),
    )
    create_use(client, patient_token, target)
    other_id, other_email = second_patient_user.id, second_patient_user.email
    stored = db_session.get(MedicalDocument, doc["id"])
    source_path = storage_service.resolve(stored.file_path)
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    plan = build_plan(db_session, request.id, admin.id, policy)
    assert source_path.is_file() and db_session.get(Patient, target) is not None  # Planning is read-only.
    assert plan["snapshot"]["prescription_revisions"]["count"] == 2
    assert plan["snapshot"]["health_sources"]["count"] == 1
    receipt = execute_plan(db_session, plan, digest(plan), patient_user.id, True, tmp_path / "progress.json")
    db_session.expire_all()
    assert not source_path.exists() and db_session.get(Patient, target) is None
    assert db_session.query(MedicalDocument).filter_by(patient_id=target).count() == 0
    archived = db_session.get(User, patient_user.id)
    assert (
        archived.email.startswith("erased-")
        and archived.full_name == "Erased account"
        and archived.phone is None
        and not archived.is_active
    )
    assert db_session.query(AuthSession).filter_by(user_id=archived.id).count() == 0
    assert db_session.get(User, other_id).email == other_email and db_session.get(User, other_id).is_active
    assert db_session.query(AuditLog).filter_by(patient_id=target).count() == 0
    assert db_session.query(AuditLog).filter_by(action="EXECUTE_APPROVED_ERASURE").count() == 1
    assert receipt["backup_erasure_performed"] is False and len(receipt["object_key_hashes"]) == 1
    blocked = client.put(
        f"/api/v1/admin/users/{archived.id}/activation",
        headers=headers(admin_token),
        json=dict(expected_active=False, active=True, evidence="Synthetic forbidden reactivation"),
    )
    assert blocked.status_code == 409


def test_plan_requires_inactive_account_reviewed_request_and_terminal_processing(
    client, patient_token, admin_token, patient_user, db_session
):
    doc = upload(client, patient_token).json()["document"]
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    with pytest.raises(ErasureError, match="queued/processing"):
        build_plan(db_session, request.id, admin.id, policy)
    job = db_session.query(DocumentProcessingJob).filter_by(document_id=doc["id"]).one()
    job.status = "failed"
    db_session.commit()
    patient_user.is_active = True
    db_session.commit()
    with pytest.raises(ErasureError, match="Deactivate"):
        build_plan(db_session, request.id, admin.id, policy)
    patient_user.is_active = False
    request.status = "closed"
    db_session.commit()
    with pytest.raises(ErasureError, match="under review"):
        build_plan(db_session, request.id, admin.id, policy)
    request.status = "under_review"
    db_session.commit()
    with pytest.raises(ErasureError, match="administrator"):
        build_plan(db_session, request.id, patient_user.id, policy)


def test_changed_plan_wrong_confirmation_and_progress_cannot_bypass_sources(
    client, patient_token, admin_token, patient_user, db_session, tmp_path
):
    doc, _ = setup_source(client, patient_token, db_session)
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    plan = build_plan(db_session, request.id, admin.id, policy)
    source = db_session.get(MedicalDocument, doc["id"])
    path = storage_service.resolve(source.file_path)
    with pytest.raises(ErasureError):
        execute_plan(db_session, plan, "wrong", patient_user.id, True, tmp_path / "progress.json")
    with pytest.raises(ErasureError):
        execute_plan(db_session, plan, digest(plan), patient_user.id, False, tmp_path / "progress.json")
    source.title = "Changed after review"
    db_session.commit()
    with pytest.raises(ErasureError, match="changed"):
        execute_plan(db_session, plan, digest(plan), patient_user.id, True, tmp_path / "progress.json")
    assert path.is_file() and db_session.get(Patient, plan["patient_id"])


def test_storage_failure_preserves_database_for_a_reviewed_retry(
    client, patient_token, admin_token, patient_user, db_session, tmp_path, monkeypatch
):
    doc, _ = setup_source(client, patient_token, db_session)
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    plan = build_plan(db_session, request.id, admin.id, policy)
    original = storage_service.get_secure_file_path

    def unavailable(*args):
        raise OSError("Synthetic storage failure")

    monkeypatch.setattr(storage_service, "get_secure_file_path", unavailable)
    with pytest.raises(OSError):
        execute_plan(db_session, plan, digest(plan), patient_user.id, True, tmp_path / "progress.json")
    assert db_session.get(MedicalDocument, doc["id"]) is not None
    monkeypatch.setattr(storage_service, "get_secure_file_path", original)
    execute_plan(db_session, plan, digest(plan), patient_user.id, True, tmp_path / "progress.json")
    assert db_session.get(Patient, plan["patient_id"]) is None


def test_erasure_receipt_recovers_after_committed_database_but_lost_output(
    client, patient_token, admin_token, patient_user, db_session, tmp_path
):
    setup_source(client, patient_token, db_session)
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    plan = build_plan(db_session, request.id, admin.id, policy)
    args = (db_session, plan, digest(plan), patient_user.id, True, tmp_path / "progress.json")
    receipt = execute_plan(*args)
    # Simulate a process stopping before its receipt file could be written.
    assert execute_plan(*args) == receipt
    assert db_session.query(AuditLog).filter_by(action="EXECUTE_APPROVED_ERASURE").count() == 1
    assert (
        json.loads(db_session.query(AuditLog).filter_by(action="EXECUTE_APPROVED_ERASURE").one().details)
        == receipt
    )


def test_external_storage_blocks_before_any_local_object_is_removed(
    client, patient_token, admin_token, patient_user, db_session, tmp_path
):
    local, _ = setup_source(client, patient_token, db_session)
    remote, _ = setup_source(client, patient_token, db_session)
    db_session.get(MedicalDocument, remote["id"]).storage_backend = "s3"
    db_session.commit()
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    plan = build_plan(db_session, request.id, admin.id, policy)
    path = storage_service.resolve(db_session.get(MedicalDocument, local["id"]).file_path)
    with pytest.raises(ErasureError, match="S3 versions/retention"):
        execute_plan(db_session, plan, digest(plan), patient_user.id, True, tmp_path / "progress.json")
    assert path.is_file() and db_session.get(Patient, plan["patient_id"])


def test_corrupt_cross_patient_source_blocks_plan_without_removing_either_patient(
    client, patient_token, admin_token, patient_user, second_patient_user, db_session
):
    doc, _ = setup_source(client, patient_token, db_session)
    record = HealthRecord(patient_id=second_patient_user.patient_profile.id, kind="lab")
    db_session.add(record)
    db_session.flush()
    revision = HealthRevision(
        record_id=record.id,
        version=1,
        title="Synthetic other patient",
        occurred_on=date(2026, 1, 1),
        data={},
        recorded_by=second_patient_user.id,
        provenance="patient_reported",
        reason="Synthetic corrupt fixture",
    )
    db_session.add(revision)
    db_session.flush()
    db_session.add(HealthSource(revision_id=revision.id, document_id=doc["id"]))
    db_session.commit()
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    with pytest.raises(ErasureError, match="Cross-patient source ownership"):
        build_plan(db_session, request.id, admin.id, policy)
    assert db_session.get(HealthRecord, record.id) and db_session.get(MedicalDocument, doc["id"])


def test_forged_progress_never_skips_existing_source_hash_validation(
    client, patient_token, admin_token, patient_user, db_session, tmp_path
):
    untouched, _ = setup_source(client, patient_token, db_session)
    doc, _ = setup_source(client, patient_token, db_session)
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    plan = build_plan(db_session, request.id, admin.id, policy)
    source = db_session.get(MedicalDocument, doc["id"])
    path = storage_service.resolve(source.file_path)
    progress = tmp_path / "progress.json"
    progress.write_text(
        json.dumps(dict(plan_sha256=digest(plan), deleted=[digest(["local", source.file_path])])),
        encoding="utf-8",
    )
    path.write_bytes(b"changed fixture after planning")
    with pytest.raises(Exception):
        execute_plan(db_session, plan, digest(plan), patient_user.id, True, progress)
    assert path.is_file() and db_session.get(Patient, plan["patient_id"])
    assert storage_service.resolve(db_session.get(MedicalDocument, untouched["id"]).file_path).is_file()


def test_outgoing_cross_patient_document_reference_also_blocks_plan(
    client, patient_token, admin_token, patient_user, second_patient_user, db_session
):
    doc, _ = setup_source(client, patient_token, db_session)
    # Invert the corruption: target's revision links another patient's document.
    db_session.get(MedicalDocument, doc["id"]).patient_id = second_patient_user.patient_profile.id
    record = HealthRecord(patient_id=patient_user.patient_profile.id, kind="lab")
    db_session.add(record)
    db_session.flush()
    revision = HealthRevision(
        record_id=record.id,
        version=1,
        title="Synthetic target record",
        occurred_on=date(2026, 1, 1),
        data={},
        recorded_by=patient_user.id,
        provenance="patient_reported",
        reason="Synthetic corrupt fixture",
    )
    db_session.add(revision)
    db_session.flush()
    db_session.add(HealthSource(revision_id=revision.id, document_id=doc["id"]))
    db_session.commit()
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    with pytest.raises(ErasureError, match="Cross-patient outgoing reference"):
        build_plan(db_session, request.id, admin.id, policy)


def test_administrative_history_changes_invalidate_reviewed_plan(
    client, patient_token, admin_token, patient_user, db_session, tmp_path
):
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    organization = Organization(
        name="Synthetic privacy organization", status="verified", evidence="Synthetic fixture"
    )
    db_session.add(organization)
    db_session.flush()
    history = OrganizationHistory(
        organization_id=organization.id,
        actor_id=admin.id,
        change=dict(user_id=patient_user.id, status="inactive"),
    )
    db_session.add(history)
    db_session.commit()
    plan = build_plan(db_session, request.id, admin.id, policy)
    assert plan["snapshot"]["organization_history_redaction"]["count"] == 1
    history.change = dict(user_id=patient_user.id, status="changed after review")
    db_session.commit()
    with pytest.raises(ErasureError, match="changed"):
        execute_plan(db_session, plan, digest(plan), patient_user.id, True, tmp_path / "progress.json")
    assert db_session.get(Patient, plan["patient_id"])


@pytest.mark.parametrize("invalid_checksum", ["", "not-a-sha256", "a" * 63])
def test_missing_or_malformed_source_checksum_blocks_read_only_plan(
    client, patient_token, admin_token, patient_user, db_session, invalid_checksum
):
    doc, _ = setup_source(client, patient_token, db_session)
    source = db_session.get(MedicalDocument, doc["id"])
    source.sha256_hash = invalid_checksum
    db_session.commit()
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    with pytest.raises(ErasureError, match="checksum"):
        build_plan(db_session, request.id, admin.id, policy)
    assert storage_service.resolve(source.file_path).is_file()


def test_unrevoked_session_and_future_retention_date_block_plan(
    client, patient_token, admin_token, patient_user, db_session
):
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    session = db_session.query(AuthSession).filter_by(user_id=patient_user.id).one()
    session.revoked_at = None
    db_session.commit()
    with pytest.raises(ErasureError, match="session"):
        build_plan(db_session, request.id, admin.id, policy)
    session.revoked_at = utc_now()
    db_session.commit()
    policy.eligible_after = datetime(2099, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ErasureError, match="eligibility date"):
        build_plan(db_session, request.id, admin.id, policy)


@pytest.mark.skipif(os.name != "nt", reason="Case aliases share a source file on Windows")
def test_case_alias_shared_with_another_patient_blocks_plan(
    client, patient_token, admin_token, patient_user, second_patient_user, db_session
):
    original, _ = setup_source(client, patient_token, db_session)
    alias, _ = setup_source(client, patient_token, db_session)
    source = db_session.get(MedicalDocument, original["id"])
    other = db_session.get(MedicalDocument, alias["id"])
    other.patient_id = second_patient_user.patient_profile.id
    other.file_path = source.file_path.upper()
    db_session.commit()
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    with pytest.raises(ErasureError, match="alias"):
        build_plan(db_session, request.id, admin.id, policy)
    assert storage_service.resolve(source.file_path).is_file()


def test_hard_linked_source_requires_operator_review(
    client, patient_token, admin_token, patient_user, db_session, tmp_path
):
    doc, _ = setup_source(client, patient_token, db_session)
    source = db_session.get(MedicalDocument, doc["id"])
    path = storage_service.resolve(source.file_path)
    os.link(path, tmp_path / "synthetic-linked-source.pdf")
    request, policy = setup_request(db_session, patient_user)
    admin = db_session.query(User).filter_by(role="admin").one()
    with pytest.raises(ErasureError, match="Hard-linked"):
        build_plan(db_session, request.id, admin.id, policy)
    assert path.is_file()
