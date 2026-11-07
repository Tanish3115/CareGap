"""Explicit offline erasure plans. No API or automatic privacy-request deletion."""

import hashlib
import json
import os
import re
import secrets
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, delete, or_, select, update
from app.database import Base
from app.core.time import utc_now
from app.core.security import hash_password
from app.models.user import User
from app.models.patient import Patient
from app.models.operations import PrivacyRequest, OrganizationHistory
from app.models.audit import AuditLog
from app.models.document import MedicalDocument
from app.models.consent import ConsentGrant
from app.models.processing import DocumentProcessingJob
from app.models.file_deletion import FileDeletion
from app.models.session import AuthSession
from app.services.storage_service import storage_service
from app.services.audit_service import audit_service


class ErasureError(ValueError):
    pass


class ErasurePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str = Field(min_length=5, max_length=200, pattern=r"^[A-Za-z0-9._:/-]+$")
    backup_procedure_reference: str = Field(min_length=5, max_length=200, pattern=r"^[A-Za-z0-9._:/-]+$")
    eligible_after: datetime
    retain_pseudonymous_account: Literal[True]

    @field_validator("eligible_after")
    @classmethod
    def require_utc(cls, value):
        if value.tzinfo is None or value.utcoffset().total_seconds() != 0:
            raise ValueError("Use an explicit UTC eligibility timestamp")
        return value.astimezone(timezone.utc)


OWNED = frozenset(
    (
        "patients",
        "medical_documents",
        "file_deletions",
        "consent_grants",
        "access_requests",
        "encounters",
        "encounter_revisions",
        "encounter_sources",
        "follow_up_tasks",
        "follow_up_revisions",
        "document_processing_jobs",
        "document_review_revisions",
        "prescription_revisions",
        "medication_entries",
        "medication_uses",
        "medication_use_revisions",
        "medication_reconciliations",
        "health_records",
        "health_revisions",
        "health_sources",
        "fhir_imports",
        "fhir_import_links",
        "notification_preferences",
        "notification_deliveries",
        "summary_processing_consents",
        "auth_sessions",
        "organization_memberships",
    )
)
# Each dependent must belong to the intended patient's primary identity, even if a
# corrupt cross-patient source FK would otherwise bring it into the deletion graph.
OWNERS = {
    "encounter_revisions": ("encounter_id", "encounters"),
    "encounter_sources": ("revision_id", "encounter_revisions"),
    "follow_up_revisions": ("task_id", "follow_up_tasks"),
    "document_processing_jobs": ("document_id", "medical_documents"),
    "document_review_revisions": ("document_id", "medical_documents"),
    "prescription_revisions": ("document_id", "medical_documents"),
    "medication_use_revisions": ("medication_use_id", "medication_uses"),
    "medication_reconciliations": ("medication_use_id", "medication_uses"),
    "health_revisions": ("record_id", "health_records"),
    "health_sources": ("revision_id", "health_revisions"),
    "fhir_import_links": ("import_id", "fhir_imports"),
}


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=lambda item: item.isoformat()
    ).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def private_json(path, value):
    """Create a new operator file; never overwrite a reviewed plan/receipt."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(value) + b"\n")


def local_path(key, patient_id=None):
    target = storage_service.resolve(key)
    raw = storage_service.base_dir / key
    for component in (raw, *raw.parents):
        if component == storage_service.base_dir:
            break
        try:
            metadata = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ErasureError("Linked source paths require operator review")
    if patient_id and not target.is_relative_to(storage_service.base_dir / patient_id):
        raise ErasureError("Source path resolves outside this patient namespace")
    if target.exists() and target.stat().st_nlink > 1:
        raise ErasureError("Hard-linked source files require operator review")
    return target


def eligibility(db, request_id, admin_id, policy):
    admin, request = db.get(User, str(admin_id)), db.get(PrivacyRequest, str(request_id))
    if not admin or admin.role != "admin" or not admin.is_active:
        raise ErasureError("An active operational administrator is required")
    if (
        not request
        or request.kind != "erasure"
        or request.status != "under_review"
        or request.decision_reference != policy.reference
    ):
        raise ErasureError("An erasure request under review must name this approved policy reference")
    user = db.get(User, request.user_id)
    patient = db.query(Patient).filter_by(user_id=user.id).one_or_none() if user else None
    if not patient or user.role != "patient" or user.doctor_profile:
        raise ErasureError("Only an existing patient-only account can be processed")
    if user.is_active:
        raise ErasureError("Deactivate the patient and revoke sessions before planning erasure")
    if db.query(AuthSession).filter(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)).count():
        raise ErasureError("Revoke every patient session before planning erasure")
    if db.query(ConsentGrant).filter_by(patient_id=patient.id, is_revoked=False).count():
        raise ErasureError("Revoke every patient grant before planning erasure")
    if (
        db.query(DocumentProcessingJob)
        .join(MedicalDocument, MedicalDocument.id == DocumentProcessingJob.document_id)
        .filter(
            MedicalDocument.patient_id == patient.id,
            DocumentProcessingJob.status.in_(("queued", "processing")),
        )
        .count()
    ):
        raise ErasureError("Stop workers and resolve queued/processing jobs before erasure")
    if db.query(FileDeletion).filter_by(patient_id=patient.id, status="pending").count():
        raise ErasureError("Finish pending document file cleanup before account erasure")
    if utc_now() < policy.eligible_after.replace(tzinfo=None):
        raise ErasureError("The approved retention eligibility date has not been reached")
    return user, patient, request


def collect(db, user, patient):
    tables = Base.metadata.tables
    rows = {name: {} for name in OWNED}

    def add(name, row):
        key = tuple(row[column.name] for column in tables[name].primary_key)
        rows[name][key] = dict(row)

    for name in OWNED:
        table = tables[name]
        condition = (
            table.c.id == patient.id
            if name == "patients"
            else (
                table.c.user_id == user.id
                if name in ("auth_sessions", "organization_memberships")
                else table.c.patient_id == patient.id
                if "patient_id" in table.c
                else None
            )
        )
        if condition is not None:
            for row in db.execute(select(table).where(condition)).mappings():
                add(name, row)
    # Reach dependent rows through declared FKs; no guessed free-text identifiers.
    for _ in range(len(OWNED)):
        before = sum(map(len, rows.values()))
        for table in Base.metadata.sorted_tables:
            clauses = []
            for fk in table.foreign_keys:
                parent = fk.column.table.name
                if parent in rows and rows[parent]:
                    values = {row[fk.column.name] for row in rows[parent].values()}
                    clauses.append(fk.parent.in_(values))
            if clauses:
                found = list(db.execute(select(table).where(or_(*clauses))).mappings())
                if found and table.name not in OWNED:
                    raise ErasureError("Unreviewed dependent table blocks erasure: " + table.name)
                for row in found:
                    add(table.name, row)
        if sum(map(len, rows.values())) == before:
            break
    for name, selected in rows.items():
        for row in selected.values():
            if "patient_id" in row and row["patient_id"] != patient.id:
                raise ErasureError("Cross-patient reference blocks erasure")
            if name in OWNERS:
                field, parent = OWNERS[name]
                if (row[field],) not in rows[parent]:
                    raise ErasureError("Cross-patient source ownership blocks erasure")
            if name == "fhir_import_links" and (row["revision_id"],) not in rows["health_revisions"]:
                raise ErasureError("Cross-patient FHIR lineage blocks erasure")
            for fk in tables[name].foreign_keys:
                parent = fk.column.table.name
                value = row[fk.parent.name]
                if (
                    parent in OWNED
                    and value is not None
                    and not any(parent_row[fk.column.name] == value for parent_row in rows[parent].values())
                ):
                    raise ErasureError("Cross-patient outgoing reference blocks erasure")
    return rows


def build_plan(db, request_id, admin_id, policy):
    user, patient, request = eligibility(db, request_id, admin_id, policy)
    rows = collect(db, user, patient)
    objects = [
        dict(key=row["file_path"], backend=row["storage_backend"], sha256=row["sha256_hash"])
        for row in rows["medical_documents"].values()
    ]
    keys = set()
    local_targets = set()
    for item in objects:
        if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ErasureError("A valid stored source checksum is required before erasure")
        if item["backend"] not in ("local", "s3") or not item["key"].startswith(patient.id + "/"):
            raise ErasureError("Unreviewed source-storage namespace blocks erasure")
        signature = (item["backend"], item["key"])
        if signature in keys:
            raise ErasureError("Shared source-storage key blocks erasure")
        keys.add(signature)
        if (
            db.query(MedicalDocument)
            .filter(MedicalDocument.file_path == item["key"], MedicalDocument.patient_id != patient.id)
            .count()
        ):
            raise ErasureError("Cross-patient source-storage key blocks erasure")
        if item["backend"] == "local":
            identity = os.path.normcase(str(local_path(item["key"], patient.id)))
            if identity in local_targets:
                raise ErasureError("Aliased source-storage paths block erasure")
            local_targets.add(identity)
    if local_targets:
        for (key,) in db.query(MedicalDocument.file_path).filter(
            MedicalDocument.patient_id != patient.id, MedicalDocument.storage_backend == "local"
        ):
            if os.path.normcase(str(local_path(key))) in local_targets:
                raise ErasureError("Cross-patient source-storage alias blocks erasure")
    audit = [
        dict(row)
        for row in db.execute(
            select(AuditLog.__table__).where(
                or_(AuditLog.patient_id == patient.id, AuditLog.actor_id == user.id)
            )
        ).mappings()
    ]
    requests = [
        dict(row)
        for row in db.execute(
            select(PrivacyRequest.__table__).where(PrivacyRequest.user_id == user.id)
        ).mappings()
    ]
    history = [
        dict(row)
        for row in db.execute(select(OrganizationHistory.__table__)).mappings()
        if row["change"].get("user_id") == user.id
    ]
    snapshot = {
        name: dict(count=len(selected), digest=digest(sorted(selected.values(), key=canonical)))
        for name, selected in rows.items()
    }
    snapshot.update(
        account=dict(
            digest=digest({column.name: getattr(user, column.name) for column in User.__table__.columns})
        ),
        audit_redaction=dict(count=len(audit), digest=digest(sorted(audit, key=canonical))),
        organization_history_redaction=dict(
            count=len(history), digest=digest(sorted(history, key=canonical))
        ),
        request_updates=dict(count=len(requests), digest=digest(sorted(requests, key=canonical))),
    )
    return dict(
        schema="caregap-erasure-plan-v1",
        request_id=request.id,
        request_version=request.version,
        admin_id=str(admin_id),
        user_id=user.id,
        patient_id=patient.id,
        policy=policy.model_dump(mode="json"),
        snapshot=snapshot,
        objects=sorted(objects, key=lambda item: (item["backend"], item["key"])),
        consequences=[
            "Current patient profile, clinical records and source objects are removed",
            "Account becomes inactive and pseudonymous; minimal administrative audit rows remain",
            "Backups, downloaded copies, third-party text and external retention remain operator responsibilities",
        ],
    )


def execute_plan(db, plan, expected_sha256, confirmed_user_id, maintenance_confirmed, progress_path):
    if (
        not maintenance_confirmed
        or confirmed_user_id != plan.get("user_id")
        or digest(plan) != expected_sha256
    ):
        raise ErasureError("Review the exact plan, confirm the user and acknowledge offline maintenance")
    policy = ErasurePolicy.model_validate(plan["policy"])
    admin = db.get(User, plan["admin_id"])
    if not admin or admin.role != "admin" or not admin.is_active:
        raise ErasureError("An active operational administrator is required")
    # The receipt is committed atomically with erasure. A lost output file can be
    # recovered by repeating the exact command without deleting anything again.
    previous = (
        db.query(AuditLog).filter_by(action="EXECUTE_APPROVED_ERASURE", resource_id=plan["request_id"]).all()
    )
    for entry in previous:
        receipt = json.loads(entry.details)
        if receipt.get("plan_sha256") == expected_sha256:
            return receipt
    if any(item["backend"] != "local" for item in plan["objects"]):
        raise ErasureError(
            "S3 versions/retention require the provider erasure procedure before local execution"
        )
    if db.bind.dialect.name == "postgresql":
        # Offline maintenance: block concurrent record changes through commit.
        from sqlalchemy import text

        names = ",".join('"' + table.name + '"' for table in Base.metadata.sorted_tables)
        db.execute(text("SET LOCAL lock_timeout = '5s'"))
        db.execute(text("LOCK TABLE " + names + " IN ACCESS EXCLUSIVE MODE"))
    fresh = build_plan(db, plan["request_id"], plan["admin_id"], policy)
    if digest(fresh) != expected_sha256:
        raise ErasureError("Records or approval changed; generate a new plan")
    progress_path = Path(progress_path)
    progress = (
        json.loads(progress_path.read_text(encoding="utf-8"))
        if progress_path.exists()
        else dict(plan_sha256=expected_sha256, deleted=[])
    )
    if progress.get("plan_sha256") != expected_sha256:
        raise ErasureError("Progress file belongs to another plan")
    completed = set(progress["deleted"])
    # Validate every remaining source before deleting the first one. Maintenance
    # prevents filesystem writers between this preflight and each deletion.
    for item in plan["objects"]:
        if local_path(item["key"], plan["patient_id"]).exists():
            storage_service.get_secure_file_path(item["key"], item["sha256"])
    for item in plan["objects"]:
        key_hash = digest([item["backend"], item["key"]])
        # Never trust a progress file as proof that a source object is gone.
        target = local_path(item["key"], plan["patient_id"])
        if target.exists():
            storage_service.get_secure_file_path(item["key"], item["sha256"])
            target.unlink()
        completed.add(key_hash)
        progress["deleted"] = sorted(completed)
        # Atomic progress updates permit safe retry after a storage failure.
        temporary = progress_path.with_name(progress_path.name + "." + secrets.token_hex(6) + ".tmp")
        private_json(temporary, progress)
        temporary.replace(progress_path)
    user, patient, request = eligibility(db, plan["request_id"], plan["admin_id"], policy)
    rows = collect(db, user, patient)
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in rows or not rows[table.name]:
            continue
        keys = list(rows[table.name])
        for start in range(0, len(keys), 200):
            conditions = [
                and_(*(column == key[index] for index, column in enumerate(table.primary_key)))
                for key in keys[start : start + 200]
            ]
            db.execute(delete(table).where(or_(*conditions)))
    db.execute(
        update(AuditLog)
        .where(or_(AuditLog.patient_id == plan["patient_id"], AuditLog.actor_id == user.id))
        .values(patient_id=None, actor_id=None, resource_id=None, ip_address=None, details=None)
    )
    # Membership-history rows are shared administrative records; remove the target account reference.
    for history in db.query(OrganizationHistory).all():
        if history.change.get("user_id") == user.id:
            history.change = {"erased_member": True, "policy_reference": policy.reference}
    db.execute(
        update(PrivacyRequest)
        .where(PrivacyRequest.user_id == user.id)
        .values(status="closed", version=PrivacyRequest.version + 1, decision_reference=policy.reference)
    )
    db.execute(
        update(User)
        .where(User.id == user.id)
        .values(
            email=f"erased-{user.id}@invalid.example",
            full_name="Erased account",
            phone=None,
            hashed_password=hash_password(secrets.token_hex(32)),
            is_active=False,
        )
    )
    receipt = dict(
        schema="caregap-erasure-receipt-v1",
        plan_sha256=expected_sha256,
        completed_at=utc_now().isoformat(),
        patient_id_hash=hashlib.sha256(plan["patient_id"].encode()).hexdigest(),
        user_id_hash=hashlib.sha256(user.id.encode()).hexdigest(),
        object_key_hashes=[hashlib.sha256(item["key"].encode()).hexdigest() for item in plan["objects"]],
        policy_reference=policy.reference,
        backup_procedure_reference=policy.backup_procedure_reference,
        deleted_rows={
            name: entry["count"]
            for name, entry in plan["snapshot"].items()
            if "count" in entry and name in OWNED
        },
        backup_erasure_performed=False,
        retained="Inactive pseudonymous account and redacted administrative audit metadata",
    )
    audit_service.log_event(
        db,
        "EXECUTE_APPROVED_ERASURE",
        "privacy_request",
        actor_id=plan["admin_id"],
        resource_id=plan["request_id"],
        details=canonical(receipt).decode("utf-8"),
        commit=False,
    )
    db.commit()
    db.expire_all()
    return receipt
