import base64
import json
from tests.test_hardening import admin_token as admin_token, grant, headers
from tests.test_clinical import create_encounter
from tests.test_health_records import BASE, payload
from tests.test_prescriptions import setup_source, generate, save_payload
from tests.test_medication_use import create as create_use

URL = "/api/v1/clinical/fhir/longitudinal"


def test_longitudinal_fhir_preserves_distinct_records_provenance_and_private_downloads(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    doc, prescription_url = setup_source(client, patient_token, db_session)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    draft = generate(client, patient_token, prescription_url)
    assert (
        client.post(
            prescription_url, headers=headers(doctor_token), json=save_payload(draft, True)
        ).status_code
        == 201
    )
    encounter = create_encounter(client, patient_token, target, source_document_ids=[doc["id"]]).json()
    task = client.post(
        "/api/v1/clinical/follow-ups",
        headers=headers(patient_token),
        json=dict(encounter_id=encounter["id"], title="Synthetic planned care", due_on="2026-01-11"),
    )
    assert task.status_code == 201
    create_use(client, patient_token, target, use_status="taking")
    client.post(
        BASE,
        headers=headers(patient_token),
        json=payload(target, dict(kind="lab", test_name="Synthetic lab")),
    )
    response = client.get(URL, headers=headers(patient_token), params=dict(patient_id=target, limit=50))
    assert response.status_code == 200, response.text
    resources = [entry["resource"] for entry in response.json()["entry"]]
    assert {
        "Patient",
        "Practitioner",
        "Encounter",
        "DocumentReference",
        "Task",
        "Observation",
        "MedicationRequest",
        "MedicationStatement",
        "Provenance",
    } <= {resource["resourceType"] for resource in resources}
    original = next(
        resource
        for resource in resources
        if resource["resourceType"] == "DocumentReference" and resource["id"] == doc["id"]
    )
    assert original["content"][0]["attachment"]["url"] == f"/api/v1/documents/{doc['id']}/download"
    assert "hash" not in original["content"][0]["attachment"]  # R4 hash is SHA-1, not our SHA-256.
    note = next(resource for resource in resources if resource["id"] == encounter["id"] + "-note")
    assert base64.b64decode(note["content"][0]["attachment"]["data"]).decode() == encounter["notes"]
    orders = [resource for resource in resources if resource["resourceType"] == "MedicationRequest"]
    assert all(resource["reportedBoolean"] and resource["status"] == "unknown" for resource in orders)
    statement = next(resource for resource in resources if resource["resourceType"] == "MedicationStatement")
    assert statement["status"] == "active" and statement["informationSource"]["reference"].endswith(target)
    assert "file_path" not in response.text and "hashed_password" not in response.text
    keys = [(resource["resourceType"], resource["id"]) for resource in resources]
    assert len(keys) == len(set(keys))


def test_longitudinal_export_filters_scopes_before_pagination_and_denies_other_roles(
    client,
    patient_token,
    doctor_token,
    second_patient_token,
    admin_token,
    patient_user,
    doctor_user,
    db_session,
):
    target = patient_user.patient_profile.id
    create_encounter(client, patient_token, target)
    client.post(
        BASE,
        headers=headers(patient_token),
        json=payload(target, dict(kind="diagnosis", condition="PRIVATE-CONDITION"), title="PRIVATE-TITLE"),
    )
    shared = client.post(
        BASE, headers=headers(patient_token), json=payload(target, dict(kind="lab", test_name="SHARED-LAB"))
    ).json()
    scoped = grant(
        db_session, patient_user, doctor_user, include_clinical_records=True, clinical_resources=["labs"]
    )
    response = client.get(URL, headers=headers(doctor_token), params=dict(patient_id=target, limit=1))
    assert response.status_code == 200, response.text
    assert "PRIVATE-" not in response.text and "Encounter" not in response.text
    assert response.json()["entry"][1]["resource"]["id"] == shared["id"]
    for token in (second_patient_token, admin_token):
        assert client.get(URL, headers=headers(token), params=dict(patient_id=target)).status_code == 403
    scoped.is_revoked = True
    db_session.commit()
    assert client.get(URL, headers=headers(doctor_token), params=dict(patient_id=target)).status_code == 403


def test_consent_export_is_patient_owned_and_never_imports_permissions(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, clinical_resources=["labs"])
    response = client.get("/api/v1/clinical/fhir/consents", headers=headers(patient_token))
    assert response.status_code == 200
    consent = next(
        entry["resource"]
        for entry in response.json()["entry"]
        if entry["resource"]["resourceType"] == "Consent"
    )
    assert consent["status"] == "active"
    assert json.loads(consent["extension"][0]["valueString"])["clinical_resources"] == ["labs"]
    assert client.get("/api/v1/clinical/fhir/consents", headers=headers(doctor_token)).status_code == 403
    imported = client.post(
        "/api/v1/clinical/fhir/import",
        headers=headers(patient_token),
        json=dict(
            patient_id=patient_user.patient_profile.id,
            bundle=response.json(),
            reason="Synthetic consent import must not create permissions",
            source_checked=True,
        ),
    )
    assert imported.status_code == 422
