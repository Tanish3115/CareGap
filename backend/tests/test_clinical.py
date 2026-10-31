"""Synthetic clinical lifecycle and consent isolation regressions."""
from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.time import utc_now
from app.models.audit import AuditLog
from app.models.clinical import EncounterRevision, FollowUpRevision
from app.models.consent import ConsentGrant
from tests.test_consent import request_access
from tests.test_hardening import admin_token, headers, upload


def encounter_payload(**overrides):
    payload = dict(occurred_on="2026-01-10", title="Synthetic consultation",
                   notes="Synthetic patient report; no medical advice.", source_document_ids=[])
    payload.update(overrides)
    return payload


def create_encounter(client, token, patient_id, **overrides):
    return client.post("/api/v1/clinical/encounters", headers=headers(token),
                       json={"patient_id": patient_id, **encounter_payload(**overrides)})


def approve_clinical(client, patient_token, doctor_token, patient_id, write=False):
    result = request_access(client, doctor_token, patient_id, scope="all",
                            include_clinical_records=True, allow_clinical_write=write)
    assert result.status_code == 201, result.text
    decision = client.post(f"/api/v1/consent/requests/{result.json()['id']}/decision",
                            headers=headers(patient_token), json={"decision": "approve"})
    assert decision.status_code == 200, decision.text


def test_encounter_corrections_retain_original_sources_and_reject_stale_edits(
    client, patient_token, patient_user, db_session,
):
    source = upload(client, patient_token).json()["document"]
    result = create_encounter(client, patient_token, patient_user.patient_profile.id,
                               source_document_ids=[source["id"], source["id"]])
    assert result.status_code == 201, result.text
    first = result.json()
    assert first["version"] == 1 and first["provenance"] == "patient_reported"
    assert [s["id"] for s in first["sources"]] == [source["id"]]
    payload = {**encounter_payload(title="Corrected synthetic visit"), "expected_version": 1,
               "correction_reason": "Correcting the visit title and source association"}
    corrected = client.put(f"/api/v1/clinical/encounters/{first['id']}", headers=headers(patient_token), json=payload)
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["version"] == 2 and corrected.json()["sources"] == []
    assert client.put(f"/api/v1/clinical/encounters/{first['id']}", headers=headers(patient_token), json=payload).status_code == 409
    history = client.get(f"/api/v1/clinical/encounters/{first['id']}/history", headers=headers(patient_token)).json()
    assert [r["version"] for r in history] == [2, 1]
    assert history[1]["title"] == first["title"] and history[1]["sources"] == first["sources"]
    assert history[0]["recorded_by"] == patient_user.id
    assert db_session.query(EncounterRevision).count() == 2
    assert db_session.query(AuditLog).filter_by(action="CORRECT_ENCOUNTER").count() == 1


@pytest.mark.parametrize("bad_source", ["other_patient", "missing"])
def test_wrong_or_missing_sources_never_create_or_correct_records(
    client, patient_token, second_patient_token, patient_user, bad_source, db_session,
):
    source_id = upload(client, second_patient_token).json()["document"]["id"] if bad_source == "other_patient" else str(uuid4())
    patient_id = patient_user.patient_profile.id
    assert create_encounter(client, patient_token, patient_id, source_document_ids=[source_id]).status_code == 422
    record = create_encounter(client, patient_token, patient_id).json()
    response = client.put(f"/api/v1/clinical/encounters/{record['id']}", headers=headers(patient_token), json={
        **encounter_payload(source_document_ids=[source_id]), "expected_version": 1, "correction_reason": "Bad source association"})
    assert response.status_code == 422
    assert db_session.query(EncounterRevision).count() == 1


def test_follow_up_outcomes_reopen_and_reschedule_preserve_versions(client, patient_token, patient_user, db_session):
    patient_id = patient_user.patient_profile.id
    encounter = create_encounter(client, patient_token, patient_id).json()
    task_in = dict(encounter_id=encounter["id"], title="Synthetic follow-up", due_on="2026-01-11")
    created = client.post("/api/v1/clinical/follow-ups", headers=headers(patient_token), json=task_in)
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["overdue"] is True
    url = f"/api/v1/clinical/follow-ups/{task['id']}"
    edit = dict(title=task["title"], due_on=task["due_on"], expected_version=1,
                status="completed", correction_reason="Reporting synthetic completion", outcome="Synthetic visit attended")
    assert client.put(url, headers=headers(patient_token), json={**edit, "outcome": " "}).status_code == 422
    completed = client.put(url, headers=headers(patient_token), json=edit)
    assert completed.status_code == 200 and completed.json()["overdue"] is False
    assert completed.json()["provenance"] == "patient_reported"
    assert client.put(url, headers=headers(patient_token), json=edit).status_code == 409
    reopened = {**edit, "expected_version": 2, "status": "pending", "outcome": None,
                "due_on": "2027-01-10", "correction_reason": "Correcting the reported completion; rescheduled"}
    assert client.put(url, headers=headers(patient_token), json=reopened).status_code == 200
    history = client.get(url + "/history", headers=headers(patient_token)).json()
    assert [r["status"] for r in history] == ["pending", "completed", "pending"]
    assert history[1]["outcome"] == "Synthetic visit attended"
    assert db_session.query(FollowUpRevision).count() == 3
    pending = client.get(f"/api/v1/clinical/follow-ups?patient_id={patient_id}&status=pending", headers=headers(patient_token))
    assert len(pending.json()) == 1 and pending.json()[0]["due_on"] == "2027-01-10"
    assert client.get(f"/api/v1/clinical/follow-ups?patient_id={patient_id}&status=completed", headers=headers(patient_token)).json() == []
    cancelled = {**reopened, "expected_version": 3, "status": "cancelled", "outcome": "Synthetic duplicate task",
                 "correction_reason": "Cancelling the duplicate follow-up"}
    assert client.put(url, headers=headers(patient_token), json=cancelled).json()["status"] == "cancelled"


@pytest.mark.parametrize("actor", ["other_patient", "admin", "doctor", "anonymous"])
def test_all_clinical_endpoints_deny_unapproved_users(
    client, patient_token, second_patient_token, doctor_token, admin_token, patient_user, actor,
):
    patient_id = patient_user.patient_profile.id
    record = create_encounter(client, patient_token, patient_id).json()
    task = client.post("/api/v1/clinical/follow-ups", headers=headers(patient_token), json={
        "encounter_id": record["id"], "title": "Synthetic task", "due_on": "2026-01-11"}).json()
    tokens = dict(other_patient=second_patient_token, admin=admin_token, doctor=doctor_token)
    auth = headers(tokens[actor]) if actor in tokens else {}
    # TestClient may retain the owner's login cookie from other flows; tokens here are bearer-only fixtures.
    expected = 401 if actor == "anonymous" else 403
    paths = [f"encounters?patient_id={patient_id}", f"encounters/{record['id']}",
             f"encounters/{record['id']}/history", f"timeline?patient_id={patient_id}",
             f"follow-ups?patient_id={patient_id}", f"follow-ups/{task['id']}", f"follow-ups/{task['id']}/history"]
    for path in paths:
        assert client.get("/api/v1/clinical/" + path, headers=auth).status_code == expected, path
    assert create_encounter(client, tokens.get(actor, ""), patient_id).status_code == expected
    assert client.put(f"/api/v1/clinical/encounters/{record['id']}", headers=auth, json={
        **encounter_payload(), "expected_version": 1, "correction_reason": "Unauthorized correction"}).status_code == expected
    assert client.post("/api/v1/clinical/follow-ups", headers=auth, json={
        "encounter_id": record["id"], "title": "Unauthorized task", "due_on": "2026-01-11"}).status_code == expected
    assert client.put(f"/api/v1/clinical/follow-ups/{task['id']}", headers=auth, json={
        "title": "Unauthorized correction", "due_on": "2026-01-11", "expected_version": 1,
        "correction_reason": "Unauthorized correction"}).status_code == expected


@pytest.mark.parametrize("scope,selected", [("all", False), ("prescriptions_only", False), ("all", True)])
def test_existing_document_grants_do_not_expand_to_clinical_access(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session, scope, selected,
):
    source = upload(client, patient_token).json()["document"]
    patient_id = patient_user.patient_profile.id
    grant = ConsentGrant(patient_id=patient_id, doctor_id=doctor_user.doctor_profile.id, scope=scope,
                         purpose="Existing document grant", valid_until=utc_now() + timedelta(hours=2),
                         document_ids=[source["id"]] if selected else None, allow_upload=True)
    db_session.add(grant)
    db_session.commit()
    assert client.get(f"/api/v1/documents/{source['id']}", headers=headers(doctor_token)).status_code == 200
    assert client.get(f"/api/v1/clinical/encounters?patient_id={patient_id}", headers=headers(doctor_token)).status_code == 403
    people = client.get("/api/v1/consent/patients", headers=headers(doctor_token)).json()
    assert people[0]["clinical_read"] is False and people[0]["clinical_write"] is False


def test_explicit_read_then_write_consent_and_patient_correction_attribution(
    client, patient_token, doctor_token, patient_user, doctor_user,
):
    patient_id = patient_user.patient_profile.id
    approve_clinical(client, patient_token, doctor_token, patient_id)
    patient_record = create_encounter(client, patient_token, patient_id).json()
    patient_task = client.post("/api/v1/clinical/follow-ups", headers=headers(patient_token), json={
        "encounter_id": patient_record["id"], "title": "Synthetic readonly task", "due_on": "2026-01-11"}).json()
    assert client.get(f"/api/v1/clinical/encounters/{patient_record['id']}/history", headers=headers(doctor_token)).status_code == 200
    assert client.get(f"/api/v1/clinical/follow-ups/{patient_task['id']}/history", headers=headers(doctor_token)).status_code == 200
    assert client.put(f"/api/v1/clinical/encounters/{patient_record['id']}", headers=headers(doctor_token), json={
        **encounter_payload(), "expected_version": 1, "correction_reason": "Readonly correction denied"}).status_code == 403
    assert client.put(f"/api/v1/clinical/follow-ups/{patient_task['id']}", headers=headers(doctor_token), json={
        "title": patient_task["title"], "due_on": patient_task["due_on"], "expected_version": 1,
        "correction_reason": "Readonly follow-up change denied"}).status_code == 403
    assert client.get(f"/api/v1/clinical/timeline?patient_id={patient_id}", headers=headers(doctor_token)).status_code == 200
    assert create_encounter(client, doctor_token, patient_id).status_code == 403
    approve_clinical(client, patient_token, doctor_token, patient_id, write=True)
    record = create_encounter(client, doctor_token, patient_id).json()
    assert record["provenance"] == "clinician_recorded" and record["recorded_by"] == doctor_user.id
    correction = client.put(f"/api/v1/clinical/encounters/{record['id']}", headers=headers(patient_token), json={
        **encounter_payload(notes="Patient's corrected account"), "expected_version": 1,
        "correction_reason": "Patient clarification of this consultation"})
    assert correction.status_code == 200
    assert correction.json()["provenance"] == "patient_reported" and correction.json()["created_by"] == doctor_user.id
    history = client.get(f"/api/v1/clinical/encounters/{record['id']}/history", headers=headers(doctor_token)).json()
    assert [r["provenance"] for r in history] == ["patient_reported", "clinician_recorded"]


@pytest.mark.parametrize("loss", ["revoked", "expired", "future", "unverified"])
def test_clinical_access_stops_after_consent_or_verification_loss(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session, loss,
):
    patient_id = patient_user.patient_profile.id
    approve_clinical(client, patient_token, doctor_token, patient_id, write=True)
    record = create_encounter(client, doctor_token, patient_id).json()
    task = client.post("/api/v1/clinical/follow-ups", headers=headers(doctor_token), json={
        "encounter_id": record["id"], "title": "Synthetic clinician task", "due_on": "2026-01-11"}).json()
    grant = db_session.query(ConsentGrant).one()
    if loss == "revoked":
        assert client.post(f"/api/v1/consent/grants/{grant.id}/revoke", headers=headers(patient_token)).status_code == 204
    elif loss == "expired":
        grant.valid_until = utc_now() - timedelta(seconds=1)
    elif loss == "future":
        grant.valid_from = utc_now() + timedelta(hours=1)
    else:
        doctor_user.doctor_profile.verification_status = "pending"
    db_session.commit()
    for path in [f"encounters/{record['id']}", f"encounters/{record['id']}/history",
                 f"follow-ups/{task['id']}", f"follow-ups/{task['id']}/history", f"timeline?patient_id={patient_id}"]:
        assert client.get("/api/v1/clinical/" + path, headers=headers(doctor_token)).status_code == 403
    assert create_encounter(client, doctor_token, patient_id).status_code == 403
    assert client.put(f"/api/v1/clinical/follow-ups/{task['id']}", headers=headers(doctor_token), json={
        "title": task["title"], "due_on": task["due_on"], "expected_version": 1,
        "correction_reason": "No longer authorized"}).status_code == 403
    assert client.get(f"/api/v1/clinical/encounters/{record['id']}", headers=headers(patient_token)).status_code == 200


def test_clinical_consent_rejects_category_selected_or_write_without_read(client, patient_token, doctor_token, patient_user):
    patient_id = patient_user.patient_profile.id
    assert request_access(client, doctor_token, patient_id, include_clinical_records=True).status_code == 422
    assert request_access(client, doctor_token, patient_id, scope="all", allow_clinical_write=True).status_code == 422
    source = upload(client, patient_token).json()["document"]
    item = request_access(client, doctor_token, patient_id, scope="all", include_clinical_records=True).json()
    assert client.post(f"/api/v1/consent/requests/{item['id']}/decision", headers=headers(patient_token), json={
        "decision": "approve", "document_ids": [source["id"]]}).status_code == 422


def test_timeline_uses_clinical_dates_filters_and_paginates_without_other_patients(
    client, patient_token, second_patient_token, patient_user, second_patient_user,
):
    patient_id = patient_user.patient_profile.id
    source = upload(client, patient_token).json()["document"]
    early = create_encounter(client, patient_token, patient_id, occurred_on="2025-01-01", title="Early synthetic visit").json()
    late = create_encounter(client, patient_token, patient_id, occurred_on="2026-01-01", title="Later synthetic visit").json()
    create_encounter(client, second_patient_token, second_patient_user.patient_profile.id, title="Other private visit")
    url = f"/api/v1/clinical/timeline?patient_id={patient_id}"
    records = client.get(url, headers=headers(patient_token)).json()
    assert [r["id"] for r in records] == [source["id"], late["id"], early["id"]]
    assert records[0]["date_basis"] == "upload_date"
    page = client.get(url + "&kind=encounter&limit=1&offset=1", headers=headers(patient_token)).json()
    assert [r["id"] for r in page] == [early["id"]]
    assert len(client.get(url + "&search=Later", headers=headers(patient_token)).json()) == 1
    assert client.get(url + "&limit=101", headers=headers(patient_token)).status_code == 422


@pytest.mark.parametrize("change", [{"notes": " "}, {"occurred_on": "2099-01-01"}, {"provenance": "clinician_recorded"}])
def test_invalid_or_forged_encounter_input_is_rejected(client, patient_token, patient_user, change):
    assert create_encounter(client, patient_token, patient_user.patient_profile.id, **change).status_code == 422
