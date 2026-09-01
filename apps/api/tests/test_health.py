"""Smoke test for the health endpoint."""

import pytest
from apps.api.app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create a test client without database connections."""
    app = create_app()
    return TestClient(app)


def test_health_returns_200(client: TestClient) -> None:
    """Health endpoint should return 200 with status fields."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "fhirgraph-api"
    assert "neo4j" in data
    assert "postgres" in data


def test_health_has_request_id(client: TestClient) -> None:
    """Response should include X-Request-ID header."""
    response = client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
