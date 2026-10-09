"""Resource provenance returns confirmed ingestion evidence without inventing it."""

from contextlib import asynccontextmanager
from typing import Any

import asyncpg
import httpx
import pytest
from apps.api.app.dependencies import get_pg_pool
from apps.api.app.routers import lineage
from fastapi import FastAPI


class Pool:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    @asynccontextmanager
    async def acquire(self):  # type: ignore[no-untyped-def]
        yield self

    async def fetch(self, query: str, *args: Any) -> list[dict[str, Any]]:
        assert args == ("Observation", "o-1")
        if self.rows == [{"legacy_schema": True}]:
            raise asyncpg.UndefinedColumnError("column e.canonical_id does not exist")
        return self.rows


async def request(path: str, rows: list[dict[str, Any]]) -> httpx.Response:
    app = FastAPI()
    app.include_router(lineage.router)
    app.dependency_overrides[get_pg_pool] = lambda: Pool(rows)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path)


async def test_provenance_reports_artifact_hash_separately_from_live_source() -> None:
    response = await request(
        "/lineage/resources/Observation/o-1",
        [
            {
                "run_id": "run-1",
                "target_system": "neo4j",
                "canonical_id": "Observation/o-1",
                "source_artifact": "ndjson/Observation.ndjson",
                "source_location": "line:7",
                "source_line": 7,
                "content_sha256": "a" * 64,
                "dataset_hash": "b" * 64,
                "transformer_version": "1",
                "target_identity": "bolt://neo4j:7687|neo4j",
                "confirmed_stage": "build_graph",
                "run_status": "completed",
            }
        ],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["resource_id"] == "Observation/o-1"
    assert data["status"] == "available"
    assert data["events"][0]["content_sha256"] == "a" * 64
    assert data["hash_scope"] == "canonical artifact JSON before server-managed metadata"


async def test_provenance_without_events_does_not_claim_success() -> None:
    response = await request("/lineage/resources/Observation/o-1", [])
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["events"] == []


async def test_provenance_on_preserved_legacy_schema_reports_unavailable() -> None:
    response = await request("/lineage/resources/Observation/o-1", [{"legacy_schema": True}])
    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["events"] == []
    assert "pipeline" in response.json()["note"]


@pytest.mark.parametrize(
    "path,status",
    [
        ("/lineage/resources/Unknown/o-1", 404),
        ("/lineage/resources/Observation/id%20with%20spaces", 422),
    ],
)
async def test_provenance_rejects_unsupported_source_identifiers(path: str, status: int) -> None:
    assert (await request(path, [])).status_code == status
