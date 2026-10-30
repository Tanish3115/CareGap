from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from app.core.identifiers import new_patient_code, patient_code_at, PATIENT_CODE_CAPACITY
from app.models.patient import Patient


def create_patient_profile(db, **fields):
    """Allocate a unique code, retrying collisions inside an isolated savepoint."""
    def candidates():
        for _ in range(8):
            yield new_patient_code()
        occupied = {code for (code,) in db.query(Patient.patient_code).all()}
        for index in range(PATIENT_CODE_CAPACITY):
            code = patient_code_at(index)
            if code not in occupied:
                yield code

    for code in candidates():
        try:
            with db.begin_nested():
                patient = Patient(patient_code=code, **fields)
                db.add(patient)
                db.flush()
            return patient
        except IntegrityError:
            if not db.query(Patient).filter_by(patient_code=code).first():
                raise
    raise HTTPException(503, "Patient ID capacity reached. Please contact support.")
