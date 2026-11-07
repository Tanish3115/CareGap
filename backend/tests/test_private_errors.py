from uuid import UUID
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
import pytest
from app.main import app


def test_unexpected_failure_never_returns_or_logs_private_exception_contents(client, caplog):
    private = "SYNTHETIC-PRIVATE-CONTENT patient@example.test password-fixture source-quote"

    def failure():
        raise ValueError(private)

    route = APIRoute("/synthetic-private-failure", endpoint=failure, methods=["GET"])
    app.router.routes.append(route)
    try:
        response = client.get("/synthetic-private-failure?search=SYNTHETIC-PRIVATE-QUERY")
        assert response.status_code == 500 and response.json() == {"detail": "Operation failed"}
        assert response.headers["Cache-Control"] == "no-store"
        UUID(response.headers["X-Request-ID"])
        assert private not in caplog.text and "SYNTHETIC-PRIVATE-QUERY" not in caplog.text
        assert response.headers["X-Request-ID"] in caplog.text
    finally:
        app.router.routes.remove(route)


@pytest.mark.parametrize(
    "body, expected_message",
    [
        (
            {"email": "synthetic@example.com", "password": "S3cret!", "full_name": "Synthetic Patient"},
            "Password must contain 12–72 characters and at most 72 UTF-8 bytes.",
        ),
        (
            {
                "email": "synthetic@example.com",
                "password": "SYNTHETIC-PASSWORD-" * 6,
                "full_name": "Synthetic Patient",
            },
            "Password must contain 12–72 characters and at most 72 UTF-8 bytes.",
        ),
        (
            {
                "email": "SYNTHETIC-PRIVATE-EMAIL",
                "password": "synthetic-password-for-test",
                "full_name": "Synthetic Patient",
            },
            "Enter a valid email address.",
        ),
        (
            {
                "email": "synthetic@example.com",
                "password": "synthetic-password-for-test",
                "full_name": "Synthetic Patient",
                "role": "SYNTHETIC-PRIVATE-ROLE",
            },
            "Choose a patient or doctor account.",
        ),
    ],
)
def test_auth_validation_never_echoes_submitted_values(client, caplog, body, expected_message):
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail == [{"type": "request_validation_error", "loc": ["request"], "msg": expected_message}]
    for value in body.values():
        assert value not in response.text and value not in caplog.text
    assert response.headers["Cache-Control"] == "no-store"
    UUID(response.headers["X-Request-ID"])


def test_invalid_json_response_does_not_echo_document_or_parser_context(client, caplog):
    private = "SYNTHETIC-PRIVATE-PRESCRIPTION"
    response = client.post(
        "/api/v1/auth/register",
        content='{"password":"' + private,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert private not in response.text and private not in caplog.text
    assert "ctx" not in response.text and "input" not in response.text


def test_nested_and_custom_validation_errors_do_not_echo_keys_types_or_messages(client, caplog):
    private = "SYNTHETIC-PRIVATE-DIAGNOSIS"

    def nested(payload: dict[str, int]):
        return payload

    def custom():
        raise RequestValidationError(
            [
                {
                    "type": private,
                    "loc": ("body", private),
                    "msg": private,
                    "input": private,
                    "ctx": {"error": ValueError(private)},
                }
            ],
            body={"clinical_text": private},
        )

    routes = [
        APIRoute("/synthetic-private-validation", endpoint=nested, methods=["POST"]),
        APIRoute("/synthetic-private-validator", endpoint=custom, methods=["POST"]),
    ]
    app.router.routes.extend(routes)
    try:
        for path in ("/synthetic-private-validation", "/synthetic-private-validator"):
            response = client.post(path, json={private: private})
            assert response.status_code == 422
            assert private not in response.text and private not in caplog.text
            assert response.json()["detail"][0]["loc"] == ["request"]
    finally:
        for route in routes:
            app.router.routes.remove(route)
