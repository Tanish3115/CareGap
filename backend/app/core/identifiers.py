import secrets

PATIENT_CODE_CAPACITY = 26_000


def patient_code_at(index: int) -> str:
    return f"{chr(ord('A') + index // 1000)}{index % 1000:03d}"


def new_patient_code() -> str:
    """Human-friendly sharing identifier; never an authorization credential."""
    return patient_code_at(secrets.randbelow(PATIENT_CODE_CAPACITY))
