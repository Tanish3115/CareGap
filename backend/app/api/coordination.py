from datetime import date, timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.api.clinical import authorize_patient, authorized_record
from app.core.errors import PermissionDeniedException
from app.core.time import utc_now
from app.models.health_record import HealthRecord, HealthRevision
from app.models.coordination import NotificationPreference, NotificationDelivery
from app.models.user import User
from app.services.health_records import CARE_KINDS, current_records, record_out
from app.services.audit_service import audit_service
from app.services.notification_provider import provider_for

router = APIRouter(tags=["Care coordination and local notifications"])


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    enabled: bool
    channels: list[Literal["in_app", "email", "sms", "whatsapp"]] = Field(min_length=1, max_length=4)
    language: Literal["en", "hi", "kn", "te", "ta", "ml"]


class Reminder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: UUID
    expected_version: int = Field(ge=1)
    reviewed: Literal[True]


def owner(user):
    if user.role != "patient":
        raise PermissionDeniedException("Only the patient can change notification preferences")
    return user.patient_profile.id


def pref_out(row):
    return dict(
        version=row.version if row else 0,
        enabled=row.enabled if row else False,
        channels=row.channels if row else ["in_app"],
        language=row.language if row else "en",
        mode="local_mock",
    )


@router.get("/notifications/preferences")
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return pref_out(db.get(NotificationPreference, owner(user)))


@router.put("/notifications/preferences")
def save_preferences(
    payload: Preferences, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    patient_id = owner(user)
    values = dict(enabled=payload.enabled, channels=sorted(set(payload.channels)), language=payload.language)
    if payload.expected_version == 0:
        row = NotificationPreference(patient_id=patient_id, version=1, **values)
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Preferences changed. Reload before saving.")
    else:
        changed = db.execute(
            update(NotificationPreference)
            .where(
                NotificationPreference.patient_id == patient_id,
                NotificationPreference.version == payload.expected_version,
            )
            .values(version=payload.expected_version + 1, **values)
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Preferences changed. Reload before saving.")
    audit_service.log_event(
        db,
        "SET_NOTIFICATION_PREFERENCES",
        "notifications",
        actor_id=user.id,
        patient_id=patient_id,
        commit=False,
    )
    db.commit()
    return pref_out(db.get(NotificationPreference, patient_id))


@router.get("/clinical/care-worklist")
def care_worklist(
    patient_id: UUID,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(patient_id)
    authorize_patient(db, user, target, request, resource="care_plans")
    today = utc_now().date()
    query = current_records(db, target).filter(
        HealthRecord.kind.in_(CARE_KINDS),
        HealthRevision.data["status"].as_string().in_(("pending", "missed", "unknown")),
        HealthRevision.data["due_on"].as_string() <= (today + timedelta(days=7)).isoformat(),
    )
    rows = (
        query.order_by(HealthRevision.data["due_on"].as_string(), HealthRecord.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = []
    for root, revision in rows:
        data = revision.data
        rules = [("staff_outreach", "Review the unresolved care status with the patient")]
        for barrier, action in (
            ("transport", "transport_referral"),
            ("cost", "financial_referral"),
            ("language", "instruction_clarification"),
            ("instructions", "instruction_clarification"),
            ("scheduling", "rescheduling"),
        ):
            if barrier in data.get("barriers", []):
                rules.append((action, f"Patient-reported barrier: {barrier}"))
        result.append(
            dict(
                record=record_out(db, root, revision),
                overdue=data["status"] == "pending" and date.fromisoformat(data["due_on"]) < today,
                rule_suggestions=[
                    dict(action=action, reason=reason) for action, reason in dict(rules).items()
                ],
                basis="Recorded care dates/status and patient-reported barriers; staff review required. No predicted treatment effect.",
            )
        )
    audit_service.log_event(db, "VIEW_CARE_WORKLIST", "care_worklist", actor_id=user.id, patient_id=target)
    return result


@router.post("/notifications/local-reminder", status_code=201)
def local_reminder(
    payload: Reminder, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    root = authorized_record(db, HealthRecord, payload.record_id, user, request, write=True)
    if root.kind not in CARE_KINDS:
        raise HTTPException(422, "Reminders apply to care events")
    pref = db.get(NotificationPreference, root.patient_id)
    if not pref or not pref.enabled:
        raise HTTPException(422, "Patient has not enabled local mock reminders")
    # Lock preferences first so opt-out and reminder creation serialize consistently.
    locked = db.execute(
        update(NotificationPreference)
        .where(
            NotificationPreference.patient_id == root.patient_id,
            NotificationPreference.version == pref.version,
            NotificationPreference.enabled.is_(True),
        )
        .values(version=NotificationPreference.version)
        .execution_options(synchronize_session=False)
    )
    changed = db.execute(
        update(HealthRecord)
        .where(HealthRecord.id == root.id, HealthRecord.version == payload.expected_version)
        .values(updated_at=HealthRecord.updated_at)
        .execution_options(synchronize_session=False)
    )
    if locked.rowcount != 1 or changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Care record or preferences changed. Reload before queuing.")
    revision = db.query(HealthRevision).filter_by(record_id=root.id, version=payload.expected_version).one()
    if revision.data["status"] not in ("pending", "missed", "unknown"):
        raise HTTPException(422, "Completed/cancelled care does not need a reminder")
    today = utc_now().date()
    if date.fromisoformat(revision.data["due_on"]) > today + timedelta(days=7):
        raise HTTPException(422, "Local reminders cover overdue care or care due within seven days")
    body = {
        "en": "CareGap: sign in to review your care item.",
        "hi": "CareGap: \u0905\u092a\u0928\u0947 \u0926\u0947\u0916\u092d\u093e\u0932 \u0915\u093e\u0930\u094d\u092f \u0915\u0940 \u0938\u092e\u0940\u0915\u094d\u0937\u093e \u0915\u0947 \u0932\u093f\u090f \u0938\u093e\u0907\u0928 \u0907\u0928 \u0915\u0930\u0947\u0902\u0964",
        "kn": "CareGap: \u0ca8\u0cbf\u0cae\u0ccd\u0cae \u0c86\u0cb0\u0cc8\u0c95\u0cc6 \u0c95\u0cbe\u0cb0\u0ccd\u0caf\u0cb5\u0ca8\u0ccd\u0ca8\u0cc1 \u0ca8\u0ccb\u0ca1\u0cb2\u0cc1 \u0cb2\u0cbe\u0c97\u0cbf\u0ca8\u0ccd \u0cae\u0cbe\u0ca1\u0cbf.",
        "te": "CareGap: \u0c2e\u0c40 \u0c38\u0c02\u0c30\u0c15\u0c4d\u0c37\u0c23 \u0c05\u0c02\u0c36\u0c3e\u0c28\u0c4d\u0c28\u0c3f \u0c1a\u0c42\u0c21\u0c1f\u0c3e\u0c28\u0c3f\u0c15\u0c3f \u0c38\u0c48\u0c28\u0c4d \u0c07\u0c28\u0c4d \u0c1a\u0c47\u0c2f\u0c02\u0c21\u0c3f.",
        "ta": "CareGap: \u0b89\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0baa\u0bb0\u0bbe\u0bae\u0bb0\u0bbf\u0baa\u0bcd\u0baa\u0bc1\u0baa\u0bcd \u0baa\u0ba3\u0bbf\u0baf\u0bc8\u0baa\u0bcd \u0baa\u0bbe\u0bb0\u0bcd\u0b95\u0bcd\u0b95 \u0b89\u0bb3\u0bcd\u0ba8\u0bc1\u0bb4\u0bc8\u0baf\u0bc1\u0b99\u0bcd\u0b95\u0bb3\u0bcd.",
        "ml": "CareGap: \u0d28\u0d3f\u0d19\u0d4d\u0d19\u0d33\u0d41\u0d1f\u0d46 \u0d2a\u0d30\u0d3f\u0d1a\u0d30\u0d23 \u0d35\u0d3f\u0d37\u0d2f\u0d02 \u0d15\u0d3e\u0d23\u0d3e\u0d7b \u0d38\u0d48\u0d7b \u0d07\u0d7b \u0d1a\u0d46\u0d2f\u0d4d\u0d2f\u0d41\u0d15.",
    }[pref.language]
    result = []
    for channel in pref.channels:
        row = (
            db.query(NotificationDelivery)
            .filter_by(
                patient_id=root.patient_id,
                record_id=root.id,
                record_version=payload.expected_version,
                channel=channel,
                service_day=today,
            )
            .first()
        )
        if not row:
            receipt = provider_for(channel).deliver(
                message=body,
                idempotency_key=f"{root.id}:{payload.expected_version}:{channel}:{today.isoformat()}",
            )
            row = NotificationDelivery(
                patient_id=root.patient_id,
                record_id=root.id,
                record_version=payload.expected_version,
                channel=channel,
                body=body,
                service_day=today,
                created_by=user.id,
                mode=receipt.mode,
                status=receipt.status,
            )
            db.add(row)
            db.flush()
        result.append(dict(id=row.id, channel=channel, mode=row.mode, status=row.status, body=row.body))
    audit_service.log_event(
        db,
        "QUEUE_LOCAL_REMINDER",
        "notifications",
        actor_id=user.id,
        patient_id=root.patient_id,
        resource_id=root.id,
        commit=False,
    )
    db.commit()
    return result


@router.get("/notifications/history")
def notification_history(
    patient_id: UUID,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(patient_id)
    authorize_patient(db, user, target, request, resource="care_plans")
    rows = (
        db.query(NotificationDelivery)
        .filter_by(patient_id=target)
        .order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = [
        dict(
            id=row.id,
            record_id=row.record_id,
            record_version=row.record_version,
            channel=row.channel,
            mode=row.mode,
            status=row.status,
            body=row.body,
            created_at=row.created_at,
            stale=db.get(HealthRecord, row.record_id).version != row.record_version,
        )
        for row in rows
    ]
    audit_service.log_event(
        db, "VIEW_NOTIFICATION_HISTORY", "notifications", actor_id=user.id, patient_id=target
    )
    return result


@router.get("/clinical/intervention-outcomes")
def intervention_outcomes(
    patient_id: UUID,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(patient_id)
    authorize_patient(db, user, target, request, resource={"interventions", "care_plans"})
    rows = (
        current_records(db, target)
        .filter(HealthRecord.kind == "intervention")
        .order_by(HealthRecord.id)
        .offset(offset)
        .limit(limit + 1)
        .all()
    )
    events = []
    groups = {}
    for root, revision in rows[:limit]:
        data = revision.data
        care = db.get(HealthRecord, data["target_id"])
        current = db.query(HealthRevision).filter_by(record_id=care.id, version=care.version).one()
        after = current.created_at > revision.created_at and care.version > data["target_version"]
        observed = current.data["status"] if after else "not_observed_after_assignment"
        group = groups.setdefault(
            data["action"],
            dict(interventions=0, documented_completed=0, documented_missed=0, unresolved_or_excluded=0),
        )
        group["interventions"] += 1
        if observed == "completed":
            group["documented_completed"] += 1
        elif observed == "missed":
            group["documented_missed"] += 1
        else:
            group["unresolved_or_excluded"] += 1
        events.append(
            dict(
                id=root.id,
                version=revision.version,
                action=data["action"],
                intervention_status=data["status"],
                intervention_outcome=data.get("outcome"),
                recorded_at=revision.created_at,
                target_id=care.id,
                assignment_target_version=data["target_version"],
                current_target_version=care.version,
                care_outcome_after_assignment=observed,
                source_path=f"/clinical/records/{root.id}",
                experiment_reference=data.get("experiment_reference"),
            )
        )
    audit_service.log_event(
        db, "VIEW_INTERVENTION_OUTCOMES", "intervention_events", actor_id=user.id, patient_id=target
    )
    return dict(
        mode="descriptive_only",
        events=events,
        group_counts=groups,
        has_more=len(rows) > limit,
        repeated_targets=len(events) - len({event["target_id"] for event in events}),
        limitations="Unadjusted recorded counts on this page, not treatment effects. Selection bias, repeated targets, concurrent interventions and missing outcomes prevent causal interpretation. Cancelled/pending/unknown or pre-assignment outcomes are not coded as missed care.",
    )
