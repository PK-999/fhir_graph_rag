"""Resolved references become edges without rewriting the FHIR source facts."""

from pathlib import Path
from typing import Any

import pytest
from pipelines.build_graph import build_graph

from libs.fhir.models.observation import Observation
from libs.fhir.references import ReferenceIndex
from libs.graph.transformer import FHIRToGraphTransformer


def observation(reference: str) -> dict[str, Any]:
    return {
        "resourceType": "Observation",
        "id": "o-1",
        "status": "final",
        "code": {"text": "Lab"},
        "subject": {"reference": reference},
    }


@pytest.mark.parametrize("reference", ["https://example.test/fhir/Patient/p-1", "urn:uuid:patient"])
def test_resolved_edges_preserve_literal_source_reference(reference: str) -> None:
    index = ReferenceIndex(service_base_url="https://example.test/fhir")
    index.add({"resourceType": "Patient", "id": "p-1"}, full_url="urn:uuid:patient")
    source = observation(reference)
    nodes, edges = FHIRToGraphTransformer().transform(
        Observation.model_validate(source), source=source, reference_index=index
    )
    assert nodes[0].properties["subject_reference"] == reference
    assert nodes[0].properties["subject_reference_canonical"] == "Patient/p-1"
    assert [(edge.source_id, edge.target_id, edge.type) for edge in edges] == [
        ("Observation/o-1", "Patient/p-1", "SUBJECT")
    ]
    assert source["subject"]["reference"] == reference


def test_contained_reference_is_preserved_without_inventing_top_level_node() -> None:
    source = observation("#p")
    source["contained"] = [{"resourceType": "Patient", "id": "p"}]
    nodes, edges = FHIRToGraphTransformer().transform(
        Observation.model_validate(source), source=source, reference_index=ReferenceIndex()
    )
    assert len(nodes) == 1 and edges == []
    assert nodes[0].properties["subject_reference"] == "#p"
    assert "subject_reference_canonical" not in nodes[0].properties


def test_external_reference_cannot_become_local_edge() -> None:
    source = observation("https://outside.test/Patient/p-1")
    with pytest.raises(ValueError, match="outside"):
        FHIRToGraphTransformer().transform(
            Observation.model_validate(source), source=source, reference_index=ReferenceIndex()
        )


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
async def test_non_json_numbers_fail_before_opening_graph_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, literal: str
) -> None:
    (tmp_path / "resources.ndjson").write_text(
        '{"resourceType":"Observation","id":"o","status":"final","code":{"text":"Lab"},"valueQuantity":{"value":'
        + literal
        + "}}\n"
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("Invalid JSON must fail before opening a graph connection")

    monkeypatch.setattr("pipelines.build_graph.Neo4jLoader", forbidden)
    with pytest.raises(ValueError, match="finite"):
        await build_graph(tmp_path, "bolt://unused:7687", "neo4j", "test")
