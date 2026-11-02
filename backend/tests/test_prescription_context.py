from copy import deepcopy
from app.services.prescription_extraction import extract_context, extract_explicit_lines
from tests.test_prescriptions import setup_source, generate, save_payload
from tests.test_hardening import grant, headers

TEXT = (
    "Doctor: Synthetic Clinician\nConsultation date: 2026-01-10\nClinic: Synthetic Clinic\n"
    "Medicine: SYNTHETIC-A\nStrength: unknown\nDose: 1 unit\nFrequency: nightly\n"
    "Follow-up: Review after the recorded test\nRecommended test: Synthetic test\n"
)


def test_multiline_candidates_and_context_have_exact_uncertain_spans():
    rows = extract_explicit_lines(TEXT)
    assert len(rows) == 1 and rows[0].dose.value == "1 unit" and rows[0].strength is None
    assert rows[0].frequency.value == "nightly"
    context = extract_context(TEXT)
    assert context.doctor_name.value == "Synthetic Clinician"
    for value in context.model_dump().values():
        for evidence in value if isinstance(value, list) else [value] if value else []:
            assert TEXT[evidence["start"] : evidence["end"]] == evidence["value"]
            assert evidence["uncertain"] and not evidence["checked"]
    ambiguous = extract_context("Visit date: 2026-01-01\nConsultation date: 2026-02-01\n")
    assert ambiguous.consultation_date is None
    assert extract_explicit_lines("Take an unclear tablet\nDose: 1 unit") == []


def test_context_confirmation_is_checked_source_bound_versioned_and_scoped(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    _, url = setup_source(client, patient_token, db_session, TEXT)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    draft = generate(client, patient_token, url)
    body = save_payload(draft, True)
    body["context"] = deepcopy(draft["context"])
    assert client.post(url, headers=headers(doctor_token), json=body).status_code == 422
    for value in body["context"].values():
        for field in value if isinstance(value, list) else [value] if value else []:
            field.update(checked=True, uncertain=False)
    forged = deepcopy(body)
    forged["context"]["doctor_name"]["value"] = "Invented clinician"
    assert client.post(url, headers=headers(doctor_token), json=forged).status_code == 422
    response = client.post(url, headers=headers(doctor_token), json=body)
    assert response.status_code == 201, response.text
    assert response.json()["context"]["clinic"]["value"] == "Synthetic Clinic"
    history = client.get(url + "/history", headers=headers(patient_token)).json()
    assert len(history) == 2 and history[1]["context"]["doctor_name"]["uncertain"]
