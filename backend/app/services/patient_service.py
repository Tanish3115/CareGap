from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.core.identifiers import new_patient_code
from app.models.patient import Patient


def create_patient_profile(db, **fields):
    """Allocate a unique code, retrying collisions inside an isolated savepoint."""
    for _ in range(8):
        code = new_patient_code()
        try:
            with db.begin_nested():
                patient = Patient(patient_code=code, **fields)
                db.add(patient)
                db.flush()
            return patient
        except IntegrityError:
            if not db.query(Patient).filter_by(patient_code=code).first():
                raise
    raise HTTPException(503, "Unable to allocate a patient ID. Please try again.")
