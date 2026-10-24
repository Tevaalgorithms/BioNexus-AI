from fastapi.testclient import TestClient

from bionexus.api.app import create_app
from bionexus.container import build_container
from tests.conftest import TOKENS


def test_api_docs_are_available_in_development_but_not_in_production(monkeypatch):
    app = build_container(TOKENS)
    assert TestClient(create_app(app)).get("/docs").status_code == 200
    monkeypatch.setenv("APP_ENV", "production")
    hidden = TestClient(create_app(app))
    assert [hidden.get(p).status_code for p in ("/docs", "/redoc", "/openapi.json")] == [
        404,
        404,
        404,
    ]
    assert hidden.get("/healthz").status_code == 200


def test_error_responses_never_echo_credentials(monkeypatch):
    client = TestClient(create_app(build_container(TOKENS)))
    response = client.get(
        "/admin/usage", headers={"Authorization": "Bearer super-secret-token-value"}
    )
    assert response.status_code == 403 and "super-secret-token-value" not in response.text
