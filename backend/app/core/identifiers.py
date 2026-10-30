import secrets


def new_patient_code() -> str:
    """Human-friendly sharing identifier; never an authorization credential."""
    return f"CG-{secrets.randbelow(90_000_000) + 10_000_000}"
