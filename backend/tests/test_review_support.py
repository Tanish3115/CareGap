from tests.test_hardening import grant, headers
from tests.test_health_records import BASE, payload


def test_literal_medication_indicators_keep_semantics_and_separate_synthetic_safety(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    for name, dose, start, end in [
        ("SYNTHETIC-A", "1 unit", "2026-01-01", "2026-01-10"),
        ("SYNTHETIC-A", "2 units", "2026-01-05", "2026-01-20"),
        ("SYNTHETIC-B", None, None, None),
    ]:
        response = client.post(
            BASE,
            headers=headers(doctor_token),
            json=payload(
                target, dict(kind="medication_order", name=name, dose=dose, start_on=start, end_on=end)
            ),
        )
        assert response.status_code == 201, response.text
    assert (
        client.post(
            BASE,
            headers=headers(patient_token),
            json=payload(target, dict(kind="allergy", substance="SYNTHETIC-A")),
        ).status_code
        == 201
    )
    reviewed = client.get(
        "/api/v1/clinical/medication-review", params={"patient_id": target}, headers=headers(doctor_token)
    ).json()
    assert (
        not reviewed["clinical_safety_checked"]
        and reviewed["clinical_knowledge_provider"] == "not_configured"
    )
    assert {row["type"] for row in reviewed["indicators"]} >= {
        "possible_duplicate",
        "differing_dose_text",
        "recorded_period_overlap",
    }
    assert {row["type"] for row in reviewed["synthetic_demonstrations"]} == {
        "synthetic_interaction",
        "synthetic_allergy_match",
    }
    assert all("SYNTHETIC" in row["message"] for row in reviewed["synthetic_demonstrations"])


def test_intervention_outcomes_are_descriptive_and_preserve_missingness(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    care = client.post(
        BASE, headers=headers(patient_token), json=payload(target, dict(kind="referral", due_on="2026-01-01"))
    ).json()
    intervention = client.post(
        BASE,
        headers=headers(doctor_token),
        json=payload(
            target,
            dict(
                kind="intervention",
                target_id=care["id"],
                target_version=1,
                action="staff_outreach",
                status="assigned",
                assigned_staff="Synthetic reviewer",
            ),
        ),
    )
    assert intervention.status_code == 201, intervention.text
    url = "/api/v1/clinical/intervention-outcomes"
    before = client.get(url, params={"patient_id": target}, headers=headers(doctor_token)).json()
    assert (
        before["mode"] == "descriptive_only"
        and before["group_counts"]["staff_outreach"]["unresolved_or_excluded"] == 1
    )
    assert (
        client.put(
            BASE + "/" + care["id"],
            headers=headers(patient_token),
            json=payload(
                data=dict(
                    kind="referral",
                    due_on="2026-01-01",
                    status="completed",
                    outcome="Synthetic attendance outcome",
                ),
                expected_version=1,
            ),
        ).status_code
        == 200
    )
    after = client.get(url, params={"patient_id": target}, headers=headers(doctor_token)).json()
    assert after["group_counts"]["staff_outreach"]["documented_completed"] == 1
    assert "not treatment effects" in after["limitations"]
