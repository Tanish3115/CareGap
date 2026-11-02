import hashlib
import json
import pytest
from app.config import settings
from app.services.approved_knowledge import evaluate_knowledge, KnowledgeCatalog
from app.services.medication_terminology import propose, load_catalog


def configured(monkeypatch, tmp_path):
    terms = dict(
        reference="SYNTHETIC-TERMINOLOGY-REVIEW",
        release="test-1",
        entries=[
            dict(
                aliases=["SYNTHETIC-" + code],
                system="urn:caregap:test-evidence",
                code=code,
                display="SYNTHETIC-" + code,
                evidence_reference="urn:caregap:test-source:" + code,
            )
            for code in ["A", "B", "C"]
        ],
    )
    raw = json.dumps(terms).encode()
    term_path = tmp_path / "terms.json"
    term_path.write_bytes(raw)
    term_sha = hashlib.sha256(raw).hexdigest()
    catalog = dict(
        schema_version="caregap-pair-evidence-v1",
        reference="SYNTHETIC-KNOWLEDGE-REVIEW",
        release="test-1",
        license_reference="SYNTHETIC software fixture; no clinical evidence",
        clinical_review_reference="SYNTHETIC test only; not independent review",
        issued_on="2000-01-01",
        expires_on="2099-01-01",
        terminology_catalog_sha256=term_sha,
        pairs=[
            dict(
                left=dict(system="urn:caregap:test-evidence", code="A"),
                right=dict(system="urn:caregap:test-evidence", code="B"),
                finding="advisory",
                message="SYNTHETIC fixture advisory; not a clinical recommendation",
                evidence_reference="urn:caregap:test-pair:A-B",
            )
        ],
    )
    path = tmp_path / "knowledge.json"
    raw = json.dumps(catalog).encode()
    path.write_bytes(raw)
    for key, value in dict(
        TERMINOLOGY_MODE="approved_catalog",
        TERMINOLOGY_CATALOG_PATH=str(term_path),
        TERMINOLOGY_CATALOG_SHA256=term_sha,
        TERMINOLOGY_CATALOG_APPROVED=True,
        TERMINOLOGY_APPROVAL_REFERENCE="SYNTHETIC-TERM-REVIEW",
        KNOWLEDGE_MODE="approved_catalog",
        KNOWLEDGE_CATALOG_PATH=str(path),
        KNOWLEDGE_CATALOG_SHA256=hashlib.sha256(raw).hexdigest(),
        KNOWLEDGE_CATALOG_APPROVED=True,
        KNOWLEDGE_APPROVAL_REFERENCE="SYNTHETIC-REVIEW",
    ).items():
        monkeypatch.setattr(settings, key, value)
    evidence = []
    for code in ["A", "B", "C"]:
        name = "SYNTHETIC-" + code
        coding = propose(name, load_catalog())["candidates"][0]
        coding.update(checked=True, uncertain=False)
        evidence.append(dict(id="synthetic-source-" + code, name=name, coding=coding))
    return path, catalog, evidence


def test_offline_pair_evidence_preserves_coverage_and_never_implies_safety(monkeypatch, tmp_path):
    _, _, evidence = configured(monkeypatch, tmp_path)
    result = evaluate_knowledge(evidence)
    assert result["status"] == "available" and result["eligible_sources"] == 3
    assert result["assessed_pairs"] == 1 and result["unassessed_pairs"] == 2
    assert result["findings"][0]["evidence_ids"] == ["synthetic-source-A", "synthetic-source-B"]
    assert (
        not result["clinical_safety_checked"]
        and result["allergy_check"] == result["dose_check"] == "not_evaluated"
    )


@pytest.mark.parametrize("change", ["unchecked", "uncertain", "forged", "synthetic", "missing"])
def test_unreviewed_or_forged_mappings_are_excluded(monkeypatch, tmp_path, change):
    _, _, evidence = configured(monkeypatch, tmp_path)
    if change == "missing":
        evidence[0]["coding"] = None
    else:
        key, value = {
            "unchecked": ("checked", False),
            "uncertain": ("uncertain", True),
            "forged": ("code", "OTHER"),
            "synthetic": ("mode", "synthetic"),
        }[change]
        evidence[0]["coding"][key] = value
    result = evaluate_knowledge(evidence)
    assert result["eligible_sources"] == 2 and result["excluded_sources"] == 1
    assert result["findings"] == [] and not result["clinical_safety_checked"]


@pytest.mark.parametrize("change", ["expired", "future", "hash", "approval", "terminology", "malformed"])
def test_unavailable_or_changed_releases_fail_closed(monkeypatch, tmp_path, change):
    path, catalog, evidence = configured(monkeypatch, tmp_path)
    if change == "hash":
        monkeypatch.setattr(settings, "KNOWLEDGE_CATALOG_SHA256", "0" * 64)
    elif change == "approval":
        monkeypatch.setattr(settings, "KNOWLEDGE_CATALOG_APPROVED", False)
    elif change == "terminology":
        monkeypatch.setattr(settings, "TERMINOLOGY_MODE", "disabled")
    else:
        if change == "expired":
            catalog["issued_on"], catalog["expires_on"] = "2000-01-01", "2001-01-01"
        elif change == "future":
            catalog["issued_on"], catalog["expires_on"] = "2098-01-01", "2099-01-01"
        else:
            catalog["unexpected_private_field"] = "must be rejected"
        raw = json.dumps(catalog).encode()
        path.write_bytes(raw)
        monkeypatch.setattr(settings, "KNOWLEDGE_CATALOG_SHA256", hashlib.sha256(raw).hexdigest())
    result = evaluate_knowledge(evidence)
    assert (
        result["status"] == "unavailable"
        and result["findings"] == []
        and not result["clinical_safety_checked"]
    )
    assert str(path) not in json.dumps(result)


def test_duplicate_and_reversed_pair_rules_are_rejected(monkeypatch, tmp_path):
    _, catalog, _ = configured(monkeypatch, tmp_path)
    row = catalog["pairs"][0]
    catalog["pairs"].append(dict(row, left=row["right"], right=row["left"]))
    with pytest.raises(ValueError):
        KnowledgeCatalog.model_validate(catalog)


def test_approved_catalog_api_uses_only_current_reviewed_source_coding(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session, monkeypatch, tmp_path
):
    from tests.test_prescriptions import setup_source, generate, save_payload
    from tests.test_hardening import grant, headers
    from app.models.document import MedicalDocument

    _, _, evidence = configured(monkeypatch, tmp_path)
    document, path = setup_source(
        client, patient_token, db_session, text="Medicine: SYNTHETIC-A\nMedicine: SYNTHETIC-B"
    )
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    draft = generate(client, patient_token, path)
    payload = save_payload(draft, True)
    for index, item in enumerate(payload["items"]):
        item["coding"] = evidence[index]["coding"]
    assert client.post(path, headers=headers(doctor_token), json=payload).status_code == 201
    url = f"/api/v1/clinical/medication-review?patient_id={patient_user.patient_profile.id}"
    result = client.get(url, headers=headers(patient_token)).json()
    assert result["approved_knowledge"]["assessed_pairs"] == 1 and not result["clinical_safety_checked"]
    doc = db_session.get(MedicalDocument, document["id"])
    doc.review_version += 1
    db_session.commit()
    assert (
        client.get(url, headers=headers(patient_token)).json()["approved_knowledge"]["eligible_sources"] == 0
    )
