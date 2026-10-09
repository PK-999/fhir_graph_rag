"""Neo4j query-boundary tests without a database or APOC installation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from libs.graph.constraints import apply_constraints_and_indexes
from libs.graph.loader import Neo4jLoader
from libs.graph.schema import GraphEdge, GraphNode


@dataclass
class RecordingResult:
    count: int

    async def single(self) -> dict[str, int]:
        return {"c": self.count}


@dataclass
class RecordingDriver:
    queries: list[tuple[str, list[dict[str, Any]]]] = field(default_factory=list)

    def session(self) -> RecordingDriver:
        return self

    async def __aenter__(self) -> RecordingDriver:
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def run(self, query: str, *, batch: list[dict[str, Any]]) -> RecordingResult:
        self.queries.append((query, batch))
        return RecordingResult(len(batch))


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch) -> tuple[Neo4jLoader, RecordingDriver]:
    driver = RecordingDriver()

    def create_driver(uri: str, auth: tuple[str, str]) -> RecordingDriver:
        return driver

    monkeypatch.setattr("libs.graph.loader.AsyncGraphDatabase.driver", create_driver)
    return Neo4jLoader(), driver


async def test_node_upserts_preserve_all_labels_without_apoc(
    database: tuple[Neo4jLoader, RecordingDriver],
) -> None:
    loader, driver = database
    nodes = [
        GraphNode(
            id="Patient/p-1", labels=["Patient", "Synthetic"], properties={"gender": "female"}
        ),
        GraphNode(id="Patient/p-2", labels=["Patient"], properties={"gender": "male"}),
        GraphNode(
            id="Patient/p-3", labels=["Patient", "Synthetic"], properties={"gender": "female"}
        ),
    ]

    assert await loader.load_nodes(nodes) == 3

    assert len(driver.queries) == 2
    synthetic_queries = [
        query for query, batch in driver.queries if batch[0]["id"] == "Patient/p-1"
    ]
    assert len(synthetic_queries) == 1
    assert "MERGE (n:Patient {id: row.id})" in synthetic_queries[0]
    assert "SET n:Synthetic" in synthetic_queries[0]
    assert all("apoc" not in query.lower() for query, _ in driver.queries)
    assert all("SET n += row.props" in query for query, _ in driver.queries)


@pytest.mark.parametrize("labels", [[], ["Patient); DELETE n; //"], ["Patient", "bad-label"]])
async def test_invalid_labels_are_rejected_before_any_write(
    database: tuple[Neo4jLoader, RecordingDriver], labels: list[str]
) -> None:
    loader, driver = database
    nodes = [
        GraphNode(id="Patient/good", labels=["Patient"]),
        GraphNode(id="Patient/bad", labels=labels),
    ]

    with pytest.raises(ValueError):
        await loader.load_nodes(nodes)

    assert not driver.queries


async def test_invalid_relationship_type_is_rejected_before_any_write(
    database: tuple[Neo4jLoader, RecordingDriver],
) -> None:
    loader, driver = database
    edges = [
        GraphEdge(source_id="Encounter/e-1", target_id="Patient/p-1", type="SUBJECT"),
        GraphEdge(
            source_id="Encounter/e-2", target_id="Patient/p-2", type="SUBJECT]->() DELETE n //"
        ),
    ]

    with pytest.raises(ValueError):
        await loader.load_edges(edges)

    assert not driver.queries


async def test_edge_endpoints_use_canonical_labels_for_indexed_lookup(
    database: tuple[Neo4jLoader, RecordingDriver],
) -> None:
    loader, driver = database
    await loader.load_edges(
        [GraphEdge(source_id="Observation/o-1", target_id="Patient/p-1", type="SUBJECT")]
    )
    query = driver.queries[0][0]
    assert "MATCH (s:Observation {id: row.source})" in query
    assert "MATCH (t:Patient {id: row.target})" in query


async def test_schema_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = Neo4jLoader()

    async def fail_query(query: str, parameters: dict[str, Any] | None = None) -> None:
        raise RuntimeError("permission denied")

    monkeypatch.setattr(loader, "run_query", fail_query)
    try:
        with pytest.raises(RuntimeError, match="permission denied"):
            await apply_constraints_and_indexes(loader)
    finally:
        await loader.close()


async def test_schema_indexes_actual_flattened_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    loader = Neo4jLoader()
    queries: list[str] = []

    async def record_query(
        query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        queries.append(query)
        return []

    monkeypatch.setattr(loader, "run_query", record_query)
    try:
        await apply_constraints_and_indexes(loader)
    finally:
        await loader.close()

    assert any("(n:Patient) ON (n.name_0_family)" in query for query in queries)
    assert any("(n:Encounter) ON (n.period_start)" in query for query in queries)
    assert any("(n:Condition) ON (n.code_coding_0_code)" in query for query in queries)
    assert any("(n:AllergyIntolerance) REQUIRE n.id IS UNIQUE" in query for query in queries)
