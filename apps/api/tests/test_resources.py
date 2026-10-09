"""Evidence source responses are exact resources and bounded upstream failures."""

import httpx
import pytest
from apps.api.app.routers import resources
from fastapi import HTTPException


@pytest.mark.parametrize(
    "status,payload,expected",
    [
        (
            200,
            {
                "resourceType": "Observation",
                "id": "o-1",
                "valueQuantity": {"value": 8.7, "unit": "%"},
            },
            200,
        ),
        (404, {"resourceType": "OperationOutcome"}, 404),
        (500, {}, 502),
        (200, {"resourceType": "Patient", "id": "o-1"}, 502),
    ],
)
async def test_resource_proxy_checks_identity_and_closes_client(
    status: int, payload: dict[str, object], expected: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json=payload))
    )
    monkeypatch.setattr(resources, "get_fhir_client", lambda: client)
    if expected == 200:
        assert await resources.get_resource("Observation", "o-1") == payload
    else:
        with pytest.raises(HTTPException) as error:
            await resources.get_resource("Observation", "o-1")
        assert error.value.status_code == expected
    assert client.is_closed
