"""Trusted registration hints; never expose validator messages or submitted values."""

GENERIC_VALIDATION_MESSAGE = "Request failed. Please try again."
REGISTRATION_MESSAGES = {
    "email": "Enter a valid email address.",
    "password": "Password must contain 12–72 characters and at most 72 UTF-8 bytes.",
    "full_name": "Full name must contain 2–255 characters.",
    "role": "Choose a patient or doctor account.",
    "phone": "Phone number must contain at most 50 characters.",
    "license_number": "Medical license number must contain at most 100 characters.",
    "specialization": "Specialization must contain at most 100 characters.",
    "hospital_affiliation": "Hospital or clinic name must contain at most 200 characters.",
}


def registration_validation_message(errors):
    # Show the first problem so the existing translated-error UI gets one exact
    # catalog key. Ignore untrusted types/messages/context and nested field names.
    if errors:
        location = errors[0].get("loc", ())
        if (
            isinstance(location, (tuple, list))
            and len(location) == 2
            and location[0] == "body"
            and isinstance(location[1], str)
        ):
            return REGISTRATION_MESSAGES.get(location[1], GENERIC_VALIDATION_MESSAGE)
    return GENERIC_VALIDATION_MESSAGE
