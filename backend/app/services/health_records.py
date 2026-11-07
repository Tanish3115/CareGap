from fastapi import HTTPException
from sqlalchemy import update
from app.models.health_record import HealthRecord, HealthRevision, HealthSource
from app.models.document import MedicalDocument
from app.models.user import User
from app.models.interoperability import FHIRImport, FHIRImportLink
from app.core.errors import PermissionDeniedException
from app.services.authorization import require_document_access, require_clinical_access

CLINICIAN_ONLY = {"medication_order", "dispensing", "confirmed_use", "intervention"}
CARE_KINDS = {"appointment", "referral", "test"}


def current_records(db, patient_id):
    return (
        db.query(HealthRecord, HealthRevision)
        .join(
            HealthRevision,
            (HealthRevision.record_id == HealthRecord.id) & (HealthRevision.version == HealthRecord.version),
        )
        .filter(HealthRecord.patient_id == patient_id)
    )


def validate_actor(user, kind):
    if kind in CLINICIAN_ONLY and user.role != "doctor":
        raise PermissionDeniedException(
            "A verified clinician with clinical write consent must record this resource"
        )


def validate_target(db, user, patient_id, data):
    if data.kind != "intervention":
        return
    require_clinical_access(db, user, patient_id, resource="care_plans")
    target = db.get(HealthRecord, str(data.target_id))
    if not target or target.patient_id != patient_id or target.kind not in CARE_KINDS:
        raise HTTPException(422, "Intervention target must be this patient's appointment, referral or test")
    locked = db.execute(
        update(HealthRecord)
        .where(HealthRecord.id == target.id, HealthRecord.version == data.target_version)
        .values(updated_at=HealthRecord.updated_at)
        .execution_options(synchronize_session=False)
    )
    if locked.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Care target changed. Reload before recording the intervention.")


def sources(db, user, patient_id, ids, request):
    ids = sorted({str(value) for value in ids})
    docs = (
        db.query(MedicalDocument)
        .filter(MedicalDocument.id.in_(ids), MedicalDocument.patient_id == patient_id)
        .all()
    )
    if len(docs) != len(ids):
        raise HTTPException(422, "Every source must belong to this patient")
    for doc in docs:
        require_document_access(db, user, doc, request)
    return [HealthSource(document_id=value) for value in ids]


def record_out(db, root, revision):
    imported = db.get(FHIRImportLink, revision.id)
    original = db.get(FHIRImport, imported.import_id) if imported else None
    target = db.get(HealthRecord, revision.data["target_id"]) if root.kind == "intervention" else None
    return dict(
        id=root.id,
        patient_id=root.patient_id,
        kind=root.kind,
        version=revision.version,
        title=revision.title,
        occurred_on=revision.occurred_on,
        data=revision.data,
        reason=revision.reason,
        provenance=revision.provenance,
        recorded_by_name=db.get(User, revision.recorded_by).full_name,
        recorded_at=revision.created_at,
        sources=[
            dict(id=link.document_id, title=link.document.title, file_name=link.document.file_name)
            for link in revision.sources
        ],
        linked_record_stale=bool(target and target.version != revision.data["target_version"]),
        external_source=dict(
            id=original.id, sha256=original.sha256, path=f"/clinical/fhir/imports/{original.id}"
        )
        if original
        else None,
    )
