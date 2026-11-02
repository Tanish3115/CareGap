from tests.test_hardening import admin_token as admin_token, headers
from tests.test_health_records import BASE, payload


def bundle(patient_id):
    return dict(
        resourceType="Bundle",
        type="collection",
        entry=[
            dict(resource=dict(resourceType="Patient", id=patient_id)),
            dict(
                resource=dict(
                    resourceType="Condition",
                    id="synthetic-condition",
                    subject=dict(reference=f"Patient/{patient_id}"),
                    code=dict(text="SYNTHETIC source condition"),
                    recordedDate="2026-01-01",
                )
            ),
        ],
    )


def test_preview_import_original_retention_export_and_correction_lineage(client, patient_token, patient_user):
    target = patient_user.patient_profile.id
    original = bundle(target)
    body = dict(
        patient_id=target, bundle=original, reason="Reviewed synthetic source bundle", source_checked=True
    )
    preview = client.post("/api/v1/clinical/fhir/preview", headers=headers(patient_token), json=body)
    assert preview.status_code == 200 and preview.json()["records"][0]["data"]["status"] == "unknown"
    imported = client.post("/api/v1/clinical/fhir/import", headers=headers(patient_token), json=body)
    assert imported.status_code == 201, imported.text
    assert (
        client.post("/api/v1/clinical/fhir/import", headers=headers(patient_token), json=body).status_code
        == 409
    )
    data = imported.json()
    source = client.get(
        "/api/v1/clinical/fhir/imports/" + data["import_id"], headers=headers(patient_token)
    ).json()
    assert source["original"] == original and source["sha256"] == data["sha256"]
    record = client.get(BASE + "/" + data["record_ids"][0], headers=headers(patient_token)).json()
    assert record["external_source"]["id"] == data["import_id"]
    corrected = client.put(
        BASE + "/" + record["id"],
        headers=headers(patient_token),
        json=payload(
            data=dict(kind="diagnosis", condition="Corrected synthetic account"), expected_version=1
        ),
    )
    assert corrected.status_code == 200 and corrected.json()["external_source"]["id"] == data["import_id"]
    exported = client.get(
        "/api/v1/clinical/fhir/export", params={"patient_id": target}, headers=headers(patient_token)
    ).json()
    condition = exported["entry"][1]["resource"]
    assert (
        condition["resourceType"] == "Condition"
        and condition["code"]["text"] == "Corrected synthetic account"
    )
    assert condition["verificationStatus"]["coding"][0]["code"] == "unconfirmed"


def test_import_rejects_foreign_subjects_executable_bundles_unsupported_types_and_malformed_objects(
    client, patient_token, patient_user
):
    target = patient_user.patient_profile.id
    for change in ("foreign", "transaction", "unsupported", "malformed", "future"):
        data = bundle(target)
        resource = data["entry"][1]["resource"]
        if change == "foreign":
            resource["subject"]["reference"] = "Patient/other"
        elif change == "transaction":
            data["type"] = "transaction"
        elif change == "unsupported":
            resource["resourceType"] = "MedicationRequest"
        elif change == "malformed":
            resource["code"] = []
        else:
            resource["recordedDate"] = "2999-01-01"
        response = client.post(
            "/api/v1/clinical/fhir/import",
            headers=headers(patient_token),
            json=dict(
                patient_id=target, bundle=data, reason="Synthetic import validation", source_checked=True
            ),
        )
        assert response.status_code == 422, (change, response.text)


def test_export_and_import_never_grant_cross_patient_or_admin_clinical_access(
    client, patient_token, second_patient_token, admin_token, patient_user
):
    target = patient_user.patient_profile.id
    for token in (second_patient_token, admin_token):
        assert (
            client.get(
                "/api/v1/clinical/fhir/export", params={"patient_id": target}, headers=headers(token)
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/clinical/fhir/import",
                headers=headers(token),
                json=dict(
                    patient_id=target,
                    bundle=bundle(target),
                    reason="Synthetic denied import",
                    source_checked=True,
                ),
            ).status_code
            == 403
        )
