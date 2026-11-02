import pytest
from tests.test_coordination import care
from tests.test_hardening import headers


@pytest.mark.parametrize("language", ["en", "hi", "kn", "te", "ta", "ml"])
def test_all_six_reminder_languages_are_saved_and_used_without_clinical_details(
    client, patient_token, patient_user, language
):
    record = care(client, patient_token, patient_user.patient_profile.id)
    pref = client.put(
        "/api/v1/notifications/preferences",
        headers=headers(patient_token),
        json=dict(expected_version=0, enabled=True, channels=["in_app"], language=language),
    )
    assert pref.status_code == 200, pref.text
    assert (
        client.get("/api/v1/notifications/preferences", headers=headers(patient_token)).json()["language"]
        == language
    )
    response = client.post(
        "/api/v1/notifications/local-reminder",
        headers=headers(patient_token),
        json=dict(record_id=record["id"], expected_version=1, reviewed=True),
    )
    assert response.status_code == 201, response.text
    delivery = response.json()[0]
    assert delivery["mode"] == "local_mock" and "Synthetic" not in delivery["body"]
    assert delivery["body"].startswith("CareGap: ") and len(delivery["body"]) < 500
    if language != "en":
        assert not delivery["body"].isascii()
    assert (
        client.put(
            "/api/v1/notifications/preferences",
            headers=headers(patient_token),
            json=dict(expected_version=1, enabled=True, channels=["in_app"], language="bn"),
        ).status_code
        == 422
    )
