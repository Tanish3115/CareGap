import json
import httpx
from app.config import settings
from tests.test_hardening import grant, headers
from tests.test_clinical_scopes import records
from tests.test_health_records import payload, BASE

URL = "/api/v1/clinical/summary-assistance"
PREF = "/api/v1/privacy/summary-processing"


def configured(monkeypatch):
    for key, value in dict(
        SUMMARY_PROVIDER="http",
        SUMMARY_PROVIDER_APPROVED=True,
        SUMMARY_PROVIDER_REFERENCE="approved-synthetic-processor-v1",
        SUMMARY_PROVIDER_URL="https://synthetic-processor.example.test/select",
    ).items():
        monkeypatch.setattr(settings, key, value)


def test_default_assistance_is_local_source_cited_and_consent_scoped(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    records(client, patient_token, target)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, clinical_resources=["labs"])
    response = client.post(URL, headers=headers(doctor_token), json=dict(patient_id=target))
    assert response.status_code == 200, response.text
    assert response.json()["mode"] == "local_source_extracts" and response.json()["interpretations"] == []
    assert [fact["category"] for fact in response.json()["facts"]] == ["lab"]
    assert "PRIVATE-" not in response.text
    assert client.get(PREF, headers=headers(patient_token)).json()["enabled"] is False
    assert (
        client.put(
            PREF,
            headers=headers(doctor_token),
            json=dict(expected_version=0, enabled=True, provider_reference="any"),
        ).status_code
        == 403
    )
    assert (
        client.put(
            PREF,
            headers=headers(patient_token),
            json=dict(
                expected_version=0, enabled=True, provider_reference=settings.SUMMARY_PROVIDER_REFERENCE
            ),
        ).status_code
        == 422
    )


def test_processor_requires_named_opt_in_and_rejects_invented_output_before_returning(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session, monkeypatch
):
    configured(monkeypatch)
    target = patient_user.patient_profile.id
    records(client, patient_token, target)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, clinical_resources=["labs"])
    calls = []
    output = {"source_keys": ["source-0"]}

    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=output)

    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    body = dict(patient_id=target)
    assert client.post(URL, headers=headers(doctor_token), json=body).status_code == 403
    assert not calls
    pref = dict(expected_version=0, enabled=True, provider_reference=settings.SUMMARY_PROVIDER_REFERENCE)
    assert client.put(PREF, headers=headers(patient_token), json=pref).status_code == 200
    response = client.post(URL, headers=headers(doctor_token), json=body)
    assert response.status_code == 200 and response.json()["facts"][0]["details"]["test_name"] == "SHARED-LAB"
    sent = json.dumps(calls[-1])
    assert "PRIVATE-" not in sent and target not in sent
    for unsupported in (
        {"source_keys": ["invented-id"]},
        {"source_keys": ["source-0", "source-0"]},
        {"source_keys": ["source-0"], "summary": "Invented clinical conclusion"},
    ):
        output.clear()
        output.update(unsupported)
        assert client.post(URL, headers=headers(doctor_token), json=body).status_code == 502
    prior = len(calls)
    monkeypatch.setattr(settings, "SUMMARY_PROVIDER_REFERENCE", "different-processor-v2")
    assert client.post(URL, headers=headers(doctor_token), json=body).status_code == 403
    assert len(calls) == prior
    monkeypatch.setattr(settings, "SUMMARY_PROVIDER_REFERENCE", pref["provider_reference"])
    assert (
        client.put(
            PREF, headers=headers(patient_token), json={**pref, "expected_version": 1, "enabled": False}
        ).status_code
        == 200
    )
    assert client.post(URL, headers=headers(doctor_token), json=body).status_code == 403
    assert len(calls) == prior
    assert (
        client.put(PREF, headers=headers(patient_token), json={**pref, "expected_version": 1}).status_code
        == 409
    )


def test_processor_error_bodies_are_not_exposed_and_unauthorized_requests_never_transmit(
    client, patient_token, second_patient_token, patient_user, monkeypatch
):
    configured(monkeypatch)
    target = patient_user.patient_profile.id
    client.post(
        BASE,
        headers=headers(patient_token),
        json=payload(target, dict(kind="lab", test_name="Synthetic lab")),
    )
    client.put(
        PREF,
        headers=headers(patient_token),
        json=dict(expected_version=0, enabled=True, provider_reference=settings.SUMMARY_PROVIDER_REFERENCE),
    )
    calls = []
    original = httpx.Client

    def handler(request):
        calls.append(True)
        return httpx.Response(500, text="PRIVATE-UPSTREAM-DATA")

    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    assert (
        client.post(URL, headers=headers(second_patient_token), json=dict(patient_id=target)).status_code
        == 403
    )
    assert not calls
    response = client.post(URL, headers=headers(patient_token), json=dict(patient_id=target))
    assert response.status_code == 502 and "PRIVATE-UPSTREAM-DATA" not in response.text
    monkeypatch.setattr(settings, "SUMMARY_PROVIDER_APPROVED", False)
    calls.clear()
    assert client.post(URL, headers=headers(patient_token), json=dict(patient_id=target)).status_code == 502
    assert not calls
