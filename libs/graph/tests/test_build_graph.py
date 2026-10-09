"""Offline graph-ingestion regression tests using serialized synthetic FHIR."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pipelines.build_graph import build_graph

from libs.graph.schema import GraphEdge, GraphNode
from libs.synthetic.config import EncounterConfig, GenerationConfig
from libs.synthetic.runner import run_generation


@dataclass
class RecordingLoader:
    """Replace only the external Neo4j boundary, keeping transformation real."""

    created: bool = False
    closed: bool = False
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    failure_at: str | None = None

    async def verify_connectivity(self) -> None:
        if self.failure_at == "connect":
            raise RuntimeError("database unavailable")

    async def close(self) -> None:
        self.closed = True

    async def run_query(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        self.queries.append(query)
        if self.failure_at == "schema":
            raise RuntimeError("schema creation failed")
        return [{"c": 1}]

    async def load_nodes(self, nodes: list[GraphNode]) -> int:
        if self.failure_at == "nodes":
            raise RuntimeError("node load failed")
        self.nodes.extend(nodes)
        return len(nodes)

    async def load_edges(self, edges: list[GraphEdge]) -> int:
        if self.failure_at == "edges":
            raise RuntimeError("edge load failed")
        self.edges.extend(edges)
        return len(edges)


@pytest.fixture
def loader(monkeypatch: pytest.MonkeyPatch) -> RecordingLoader:
    instance = RecordingLoader()

    def create_loader(uri: str, auth: tuple[str, str]) -> RecordingLoader:
        instance.created = True
        return instance

    monkeypatch.setattr("pipelines.build_graph.Neo4jLoader", create_loader)
    return instance


@pytest.fixture
def generated_dataset(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    output_dir = tmp_path / "dataset"
    summary = run_generation(
        GenerationConfig(
            seed=20260830,
            patient_count=2,
            encounters=EncounterConfig(min_per_patient=10, max_per_patient=10),
            output_dir=str(output_dir),
        )
    )
    return output_dir / "ndjson", summary


def write_records(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(record) + "\n" for record in records))


async def test_generated_dataset_preserves_encounter_class_and_clinical_references(
    generated_dataset: tuple[Path, dict[str, Any]], loader: RecordingLoader
) -> None:
    ndjson_path, summary = generated_dataset
    encounter = json.loads((ndjson_path / "Encounter.ndjson").read_text().splitlines()[0])
    condition = json.loads((ndjson_path / "Condition.ndjson").read_text().splitlines()[0])

    result = await build_graph(ndjson_path, "bolt://test", "test", "test")

    assert result["success"] is True
    assert result["nodes_loaded"] == summary["total_resources"]
    nodes = {node.id: node for node in loader.nodes}
    encounter_node = nodes[f"Encounter/{encounter['id']}"]
    assert encounter_node.properties["class_code"] == encounter["class"]["code"]
    assert encounter_node.properties["period_start"] == encounter["period"]["start"]
    condition_node = nodes[f"Condition/{condition['id']}"]
    assert condition_node.properties["code_coding_0_code"] == condition["code"]["coding"][0]["code"]
    assert condition_node.properties["subject_reference"] == condition["subject"]["reference"]
    assert (
        GraphEdge(
            source_id=condition_node.id, target_id=condition["subject"]["reference"], type="SUBJECT"
        )
        in loader.edges
    )
    assert (
        GraphEdge(
            source_id=condition_node.id,
            target_id=condition["encounter"]["reference"],
            type="ENCOUNTER",
        )
        in loader.edges
    )
    assert all(edge.source_id in nodes and edge.target_id in nodes for edge in loader.edges)
    assert loader.closed


async def test_same_encounter_does_not_automatically_imply_clinical_support(
    generated_dataset: tuple[Path, dict[str, Any]], loader: RecordingLoader
) -> None:
    ndjson_path, _ = generated_dataset

    result = await build_graph(ndjson_path, "bolt://test", "test", "test")

    assert result["derived_edges"] == 0
    assert result["edges_loaded"] == len(loader.edges)
    assert all("SUPPORTED_BY" not in query for query in loader.queries)


@pytest.mark.parametrize(
    "invalid_line",
    [
        "{",
        "[]",
        '{"resourceType": "Patient"}',
        '{"resourceType": "UnknownResource", "id": "unknown"}',
        '{"resourceType": "Patient", "id": "p-1"}',
    ],
    ids=["malformed-json", "non-object", "missing-id", "unsupported-type", "duplicate-id"],
)
async def test_invalid_input_fails_with_location_before_opening_neo4j(
    tmp_path: Path, loader: RecordingLoader, invalid_line: str
) -> None:
    input_path = tmp_path / "records.ndjson"
    input_path.write_text('{"resourceType": "Patient", "id": "p-1"}\n' + invalid_line + "\n")

    with pytest.raises(ValueError, match=r"records\.ndjson:2"):
        await build_graph(input_path, "bolt://test", "test", "test")

    assert not loader.created
    assert not loader.nodes
    assert not loader.edges


async def test_dangling_reference_in_unmodeled_fhir_field_fails_before_neo4j(
    tmp_path: Path, loader: RecordingLoader
) -> None:
    input_path = tmp_path / "records.ndjson"
    write_records(
        input_path,
        [
            {
                "resourceType": "Patient",
                "id": "p-1",
                "generalPractitioner": [{"reference": "Practitioner/missing"}],
            }
        ],
    )

    with pytest.raises(ValueError, match="Practitioner/missing"):
        await build_graph(input_path, "bolt://test", "test", "test")

    assert not loader.created


@pytest.mark.parametrize("reference", ["missing", "", None, 42, "#contained", "urn:uuid:missing"])
async def test_unsupported_reference_forms_fail_before_neo4j(
    tmp_path: Path, loader: RecordingLoader, reference: object
) -> None:
    input_path = tmp_path / "records.ndjson"
    write_records(
        input_path,
        [
            {
                "resourceType": "Patient",
                "id": "p-1",
                "generalPractitioner": [{"reference": reference}],
            }
        ],
    )

    with pytest.raises(ValueError, match="reference"):
        await build_graph(input_path, "bolt://test", "test", "test")

    assert not loader.created


@pytest.mark.parametrize("resource_id", ["", "id/with/slash", "id with space", "x" * 65])
async def test_invalid_fhir_ids_fail_before_neo4j(
    tmp_path: Path, loader: RecordingLoader, resource_id: str
) -> None:
    input_path = tmp_path / "records.ndjson"
    write_records(input_path, [{"resourceType": "Patient", "id": resource_id}])

    with pytest.raises(ValueError, match="ID"):
        await build_graph(input_path, "bolt://test", "test", "test")

    assert not loader.created


async def test_unmodeled_fhir_fields_and_resolving_references_are_preserved(
    tmp_path: Path, loader: RecordingLoader
) -> None:
    input_path = tmp_path / "records.ndjson"
    write_records(
        input_path,
        [
            {"resourceType": "Practitioner", "id": "pr-1"},
            {
                "resourceType": "Patient",
                "id": "p-1",
                "meta": {"source": "synthetic-test"},
                "generalPractitioner": [{"reference": "Practitioner/pr-1"}],
            },
        ],
    )

    await build_graph(input_path, "bolt://test", "test", "test")

    patient = next(node for node in loader.nodes if node.id == "Patient/p-1")
    assert patient.properties["meta_source"] == "synthetic-test"
    assert patient.properties["general_practitioner_0_reference"] == "Practitioner/pr-1"
    assert any(edge.target_id == "Practitioner/pr-1" for edge in loader.edges)


async def test_invalid_reference_path_is_rejected_before_neo4j(
    tmp_path: Path, loader: RecordingLoader
) -> None:
    input_path = tmp_path / "records.ndjson"
    write_records(
        input_path,
        [
            {"resourceType": "Practitioner", "id": "pr-1"},
            {"resourceType": "Patient", "id": "p-1", "bad-key": {"reference": "Practitioner/pr-1"}},
        ],
    )

    with pytest.raises(ValueError, match="reference"):
        await build_graph(input_path, "bolt://test", "test", "test")

    assert not loader.created


@pytest.mark.parametrize("empty_kind", ["directory", "file"])
async def test_empty_input_is_rejected_before_neo4j(
    tmp_path: Path, loader: RecordingLoader, empty_kind: str
) -> None:
    input_path = tmp_path / "empty"
    if empty_kind == "directory":
        input_path.mkdir()
    else:
        input_path.write_text("\n")

    with pytest.raises(ValueError, match="No"):
        await build_graph(input_path, "bolt://test", "test", "test")

    assert not loader.created


@pytest.mark.parametrize("failure_at", ["connect", "schema", "nodes", "edges"])
async def test_loader_is_closed_when_database_work_fails(
    tmp_path: Path, loader: RecordingLoader, failure_at: str
) -> None:
    input_path = tmp_path / "records.ndjson"
    write_records(input_path, [{"resourceType": "Patient", "id": "p-1"}])
    loader.failure_at = failure_at

    with pytest.raises(RuntimeError):
        await build_graph(input_path, "bolt://test", "test", "test")

    assert loader.closed
