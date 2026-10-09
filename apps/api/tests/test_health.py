"""Behavior tests for API liveness and dependency readiness."""

from types import SimpleNamespace

import pytest
from apps.api.app.dependencies import db
from apps.api.app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create a test client without database connections."""
    app = create_app()
    return TestClient(app)


def test_liveness_does_not_claim_dependency_health(client: TestClient) -> None:
    """A live process must not imply its external dependencies are ready."""
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "fhirgraph-api"}


def test_readiness_returns_503_and_names_unavailable_dependency(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed Neo4j probe must make readiness fail visibly."""

    async def degraded_readiness() -> SimpleNamespace:
        return SimpleNamespace(
            ready=False,
            dependencies={
                "neo4j": SimpleNamespace(ready=False, detail="unreachable"),
                "postgres": SimpleNamespace(ready=True, detail=None),
                "hapi": SimpleNamespace(ready=True, detail=None),
            },
        )

    monkeypatch.setattr(db, "readiness", degraded_readiness, raising=False)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "service": "fhirgraph-api",
        "dependencies": {
            "neo4j": {"ready": False, "detail": "unreachable"},
            "postgres": {"ready": True, "detail": None},
            "hapi": {"ready": True, "detail": None},
        },
    }


def test_readiness_returns_200_only_when_every_dependency_is_ready(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Readiness succeeds only when every required dependency responds."""

    async def ready() -> SimpleNamespace:
        return SimpleNamespace(
            ready=True,
            dependencies={
                name: SimpleNamespace(ready=True, detail=None)
                for name in ("neo4j", "postgres", "hapi")
            },
        )

    monkeypatch.setattr(db, "readiness", ready, raising=False)
    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_legacy_health_endpoint_uses_truthful_readiness(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The compatibility endpoint must not preserve the false-positive behavior."""

    async def degraded_readiness() -> SimpleNamespace:
        return SimpleNamespace(
            ready=False,
            dependencies={
                "neo4j": SimpleNamespace(ready=False, detail="unreachable"),
                "postgres": SimpleNamespace(ready=True, detail=None),
                "hapi": SimpleNamespace(ready=True, detail=None),
            },
        )

    monkeypatch.setattr(db, "readiness", degraded_readiness, raising=False)
    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"


def test_health_has_request_id(client: TestClient) -> None:
    """Response should include X-Request-ID header."""
    response = client.get("/api/v1/health/live")
    assert "X-Request-ID" in response.headers


def test_cors_allows_the_default_fhirgraph_web_origin(client: TestClient) -> None:
    """The collision-safe default web port must be allowed to call the API."""
    response = client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "http://localhost:4010",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4010"
