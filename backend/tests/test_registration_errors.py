import pytest
from sqlalchemy import func, select

from app.core.registration_errors import registration_validation_message
from app.models.user import User


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("email", "PRIVATE-INVALID-EMAIL", "Enter a valid email address."),
        ("password", "short", "Password must contain 12–72 characters and at most 72 UTF-8 bytes."),
        ("password", "密" * 25, "Password must contain 12–72 characters and at most 72 UTF-8 bytes."),
        ("full_name", "X", "Full name must contain 2–255 characters."),
        ("phone", "x" * 51, "Phone number must contain at most 50 characters."),
        ("license_number", "x" * 101, "Medical license number must contain at most 100 characters."),
        ("specialization", "x" * 101, "Specialization must contain at most 100 characters."),
        ("hospital_affiliation", "x" * 201, "Hospital or clinic name must contain at most 200 characters."),
    ],
)
def test_doctor_gets_actionable_private_validation(client, db_session, caplog, field, value, expected):
    payload = dict(
        email="synthetic-doctor@example.com",
        password="SyntheticPassword123!",
        full_name="Synthetic Doctor",
        role="doctor",
        license_number="SYNTHETIC-REGISTRATION-TEST",
        specialization="Synthetic testing",
    )
    payload[field] = value
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"] == [
        {"type": "request_validation_error", "loc": ["request"], "msg": expected}
    ]
    assert value not in response.text and payload["password"] not in caplog.text
    assert db_session.scalar(select(func.count()).select_from(User)) == 0


def test_validation_hint_does_not_trust_custom_validator_prose_or_nested_keys():
    private = "SYNTHETIC-PRIVATE-VALIDATION"
    assert (
        registration_validation_message(
            [{"loc": ("body", "email"), "msg": private, "type": private, "input": private}]
        )
        == "Enter a valid email address."
    )
    for location in [("body", private), ("body", "email", private), ("query", "email")]:
        assert (
            registration_validation_message([{"loc": location, "msg": private, "input": private}])
            == "Request failed. Please try again."
        )
