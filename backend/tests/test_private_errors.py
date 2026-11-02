from uuid import UUID
from fastapi.routing import APIRoute
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
