from tests.test_hardening import admin_token as admin_token, grant, headers
from tests.test_health_records import BASE, payload
from app.models.coordination import NotificationDelivery


def care(client, token, target, **changes):
    data = dict(kind="referral", due_on="2026-01-01", barriers=["transport", "cost"])
    data.update(changes)
    response = client.post(BASE, headers=headers(token), json=payload(target, data))
    assert response.status_code == 201, response.text
    return response.json()


def test_worklist_rules_completed_outcomes_and_mock_notification_preferences(
    client, patient_token, patient_user, db_session
):
    target = patient_user.patient_profile.id
    record = care(client, patient_token, target)
    worklist = client.get(
        "/api/v1/clinical/care-worklist", params={"patient_id": target}, headers=headers(patient_token)
    ).json()
    assert worklist[0]["overdue"]
    assert {row["action"] for row in worklist[0]["rule_suggestions"]} == {
        "staff_outreach",
        "transport_referral",
        "financial_referral",
    }
    url = "/api/v1/notifications/local-reminder"
    body = dict(record_id=record["id"], expected_version=1, reviewed=True)
    assert client.post(url, headers=headers(patient_token), json=body).status_code == 422
    prefs = dict(expected_version=0, enabled=True, channels=["in_app", "sms"], language="hi")
    saved = client.put("/api/v1/notifications/preferences", headers=headers(patient_token), json=prefs)
    assert saved.status_code == 200 and saved.json()["version"] == 1
    assert (
        client.put(
            "/api/v1/notifications/preferences", headers=headers(patient_token), json=prefs
        ).status_code
        == 409
    )
    first = client.post(url, headers=headers(patient_token), json=body)
    assert first.status_code == 201 and len(first.json()) == 2
    assert all(row["mode"] == "local_mock" and "Synthetic" not in row["body"] for row in first.json())
    assert client.post(url, headers=headers(patient_token), json=body).json() == first.json()
    assert db_session.query(NotificationDelivery).count() == 2
    corrected = client.put(
        f"{BASE}/{record['id']}",
        headers=headers(patient_token),
        json=payload(
            data=dict(
                kind="referral",
                due_on="2026-01-01",
                status="completed",
                outcome="Synthetic patient attendance",
            ),
            expected_version=1,
        ),
    )
    assert corrected.status_code == 200
    assert (
        client.get(
            "/api/v1/clinical/care-worklist", params={"patient_id": target}, headers=headers(patient_token)
        ).json()
        == []
    )
    assert client.post(url, headers=headers(patient_token), json=body).status_code == 409
    history = client.get(
        "/api/v1/notifications/history", params={"patient_id": target}, headers=headers(patient_token)
    ).json()
    assert all(row["stale"] for row in history)


def test_care_notifications_and_decision_views_require_consent(
    client,
    patient_token,
    second_patient_token,
    doctor_token,
    admin_token,
    patient_user,
    doctor_user,
    db_session,
):
    target = patient_user.patient_profile.id
    care(client, patient_token, target)
    paths = (
        "/clinical/care-worklist",
        "/notifications/history",
        "/clinical/overview",
        "/clinical/medication-review",
        "/clinical/intervention-outcomes",
    )
    for token in (second_patient_token, doctor_token, admin_token):
        for path in paths:
            assert (
                client.get(
                    "/api/v1" + path, params={"patient_id": target}, headers=headers(token)
                ).status_code
                == 403
            )
    clinical = grant(db_session, patient_user, doctor_user, include_clinical_records=True)
    for path in paths:
        response = client.get("/api/v1" + path, params={"patient_id": target}, headers=headers(doctor_token))
        assert response.status_code == 200, response.text
    overview = client.get(
        "/api/v1/clinical/overview", params={"patient_id": target}, headers=headers(patient_token)
    ).json()
    assert overview["mode"] == "source_extracts" and not overview["interpretations"]
    assert overview["facts"][0]["source_path"].startswith("/clinical/records/")
    clinical.is_revoked = True
    db_session.commit()
    for path in paths:
        assert (
            client.get(
                "/api/v1" + path, params={"patient_id": target}, headers=headers(doctor_token)
            ).status_code
            == 403
        )


def test_synthetic_model_api_never_accepts_a_patient_identifier(client, patient_token):
    url = "/api/v1/research/synthetic-risk"
    assert client.get(url).status_code == 401
    evaluation = client.get(url, headers=headers(patient_token)).json()
    assert evaluation["mode"] == "synthetic_only" and all(evaluation["leakage_checks"].values())
    case = dict(
        prior_missed=2, prior_incomplete_referrals=1, days_since_visit=30, lead_days=7, barrier_count=1
    )
    assert client.post(url, headers=headers(patient_token), json=case).json()["mode"] == "synthetic_only"
    assert (
        client.post(url, headers=headers(patient_token), json={**case, "patient_id": "forbidden"}).status_code
        == 422
    )
