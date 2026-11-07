from tests.test_hardening import admin_token as admin_token, grant, headers
from tests.test_health_records import BASE, payload
from tests.test_clinical import create_encounter
from tests.test_interoperability import bundle
from tests.test_prescriptions import setup_source, generate, save_payload
from app.models.health_record import HealthRecord


def records(client, token, patient):
    result = {}
    for kind, data in [
        ("diagnosis", dict(condition="PRIVATE-DIAGNOSIS")),
        ("allergy", dict(substance="PRIVATE-ALLERGY")),
        ("lab", dict(test_name="SHARED-LAB", value="source text")),
        ("referral", dict(due_on="2026-01-01")),
    ]:
        response = client.post(
            BASE, headers=headers(token), json=payload(patient, {**data, "kind": kind}, title=f"{kind} title")
        )
        assert response.status_code == 201, response.text
        result[kind] = response.json()
    return result


def test_scopes_filter_lists_summaries_exports_and_writes_before_pagination(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    rows = records(client, patient_token, target)
    encounter = create_encounter(client, patient_token, target).json()
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, clinical_resources=["labs"])
    auth = headers(doctor_token)
    listed = client.get(BASE, params={"patient_id": target, "limit": 1}, headers=auth)
    assert listed.status_code == 200 and [row["kind"] for row in listed.json()] == ["lab"]
    for path in (
        BASE + "/" + rows["diagnosis"]["id"],
        BASE + "/" + rows["allergy"]["id"] + "/history",
        f"/api/v1/clinical/encounters/{encounter['id']}",
        f"/api/v1/clinical/follow-ups?patient_id={target}",
        f"/api/v1/clinical/care-worklist?patient_id={target}",
        f"/api/v1/medications?patient_id={target}",
    ):
        assert client.get(path, headers=auth).status_code == 403, path
    assert (
        client.get(BASE, params={"patient_id": target, "kind": "diagnosis"}, headers=auth).status_code == 403
    )
    assert (
        client.post(
            BASE, headers=auth, json=payload(target, dict(kind="lab", test_name="Denied write"))
        ).status_code
        == 403
    )
    overview = client.get("/api/v1/clinical/overview", params={"patient_id": target}, headers=auth)
    assert overview.status_code == 200 and [fact["category"] for fact in overview.json()["facts"]] == ["lab"]
    assert "PRIVATE-DIAGNOSIS" not in overview.text and "PRIVATE-ALLERGY" not in overview.text
    exported = client.get(
        "/api/v1/clinical/fhir/export", params={"patient_id": target, "limit": 1}, headers=auth
    )
    assert exported.status_code == 200 and [
        row["resource"]["resourceType"] for row in exported.json()["entry"]
    ] == ["Patient", "Observation"]
    capabilities = client.get("/api/v1/consent/patients", headers=auth).json()[0]
    assert (
        capabilities["clinical_read_resources"] == ["labs"] and capabilities["clinical_write_resources"] == []
    )
    grant(
        db_session,
        patient_user,
        doctor_user,
        include_clinical_records=True,
        allow_clinical_write=True,
        clinical_resources=["diagnoses"],
    )
    assert (
        client.post(
            BASE,
            headers=auth,
            json=payload(target, dict(kind="diagnosis", condition="Permitted clinician account")),
        ).status_code
        == 201
    )
    assert (
        client.post(
            BASE, headers=auth, json=payload(target, dict(kind="lab", test_name="Still denied write"))
        ).status_code
        == 403
    )


def test_patient_can_reduce_requests_but_cannot_expand_them(
    client, patient_token, doctor_token, patient_user
):
    body = dict(
        patient_id=patient_user.patient_profile.id,
        scope="all",
        purpose="Scoped synthetic review",
        include_clinical_records=True,
        clinical_resources=["labs", "diagnoses"],
    )
    created = client.post("/api/v1/consent/requests", headers=headers(doctor_token), json=body)
    assert created.status_code == 201, created.text
    url = f"/api/v1/consent/requests/{created.json()['id']}/decision"
    assert (
        client.post(
            url,
            headers=headers(patient_token),
            json=dict(decision="approve", clinical_resources=["allergies"]),
        ).status_code
        == 422
    )
    approved = client.post(
        url, headers=headers(patient_token), json=dict(decision="approve", clinical_resources=["labs"])
    )
    assert approved.status_code == 200 and approved.json()["granted_clinical_resources"] == ["labs"]
    assert approved.json()["clinical_resources"] == ["diagnoses", "labs"]
    assert client.get("/api/v1/consent/grants", headers=headers(patient_token)).json()[0][
        "clinical_resources"
    ] == ["labs"]
    for extra in (
        dict(include_clinical_records=False, clinical_resources=["labs"]),
        dict(clinical_resources=[]),
        dict(clinical_resources=["unknown"]),
        dict(clinical_resources=["interventions"]),
    ):
        assert (
            client.post(
                "/api/v1/consent/requests", headers=headers(doctor_token), json={**body, **extra}
            ).status_code
            == 422
        )


def test_fhir_original_requires_all_groups_in_source_and_import_is_atomic(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    original = bundle(target)
    original["entry"].append(
        dict(
            resource=dict(
                resourceType="Observation",
                id="shared-lab",
                subject=dict(reference=f"Patient/{target}"),
                code=dict(text="SHARED-LAB"),
                effectiveDateTime="2026-01-01",
                valueString="source",
            )
        )
    )
    body = dict(
        patient_id=target, bundle=original, reason="Synthetic complete source review", source_checked=True
    )
    imported = client.post("/api/v1/clinical/fhir/import", headers=headers(patient_token), json=body)
    assert imported.status_code == 201
    grant(
        db_session,
        patient_user,
        doctor_user,
        include_clinical_records=True,
        allow_clinical_write=True,
        clinical_resources=["labs"],
    )
    path = "/api/v1/clinical/fhir/imports/" + imported.json()["import_id"]
    assert client.get(path, headers=headers(doctor_token)).status_code == 403
    count = db_session.query(HealthRecord).count()
    assert (
        client.post("/api/v1/clinical/fhir/preview", headers=headers(doctor_token), json=body).status_code
        == 403
    )
    assert (
        client.post("/api/v1/clinical/fhir/import", headers=headers(doctor_token), json=body).status_code
        == 403
    )
    assert db_session.query(HealthRecord).count() == count


def test_prescription_and_source_review_scopes_do_not_imply_each_other(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    doc, url = setup_source(client, patient_token, db_session)
    full = grant(
        db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True
    )
    draft = generate(client, patient_token, url)
    assert client.post(url, headers=headers(doctor_token), json=save_payload(draft, True)).status_code == 201
    full.is_revoked = True
    db_session.commit()
    scoped = grant(
        db_session,
        patient_user,
        doctor_user,
        include_clinical_records=True,
        clinical_resources=["medications"],
    )
    auth = headers(doctor_token)
    target = patient_user.patient_profile.id
    assert client.get(f"/api/v1/medications?patient_id={target}", headers=auth).status_code == 200
    assert client.get(f"/api/v1/documents/{doc['id']}/review", headers=auth).status_code == 403
    assert client.get(url, headers=auth).status_code == 403
    flags = client.get(f"/api/v1/documents/{doc['id']}/processing", headers=auth).json()
    assert not flags["can_view_review"] and not flags["can_view_prescription"]
    scoped.clinical_resources = ["source_reviews"]
    db_session.commit()
    flags = client.get(f"/api/v1/documents/{doc['id']}/processing", headers=auth).json()
    assert flags["can_view_review"] and not flags["can_view_prescription"]
    assert client.get(url, headers=auth).status_code == 403


def test_malformed_grants_revocation_and_admin_access_fail_closed(
    client, patient_token, doctor_token, admin_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    row = records(client, patient_token, target)["lab"]
    scoped = grant(
        db_session,
        patient_user,
        doctor_user,
        include_clinical_records=True,
        clinical_resources=["labs", "unknown"],
    )
    url = BASE + "/" + row["id"]
    assert client.get(url, headers=headers(doctor_token)).status_code == 403
    for malformed in (None, [], ["interventions"], "labs", {"labs": True}):
        scoped.clinical_resources = malformed
        db_session.commit()
        assert client.get(url, headers=headers(doctor_token)).status_code == 403
    scoped.clinical_resources = ["labs"]
    db_session.commit()
    assert client.get(url, headers=headers(doctor_token)).status_code == 200
    scoped.is_revoked = True
    db_session.commit()
    assert client.get(url + "/history", headers=headers(doctor_token)).status_code == 403
    assert client.get(url, headers=headers(admin_token)).status_code == 403
