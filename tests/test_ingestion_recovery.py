"""Recover real ingestion with only the external store boundary replaced."""

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pipelines import build_graph, load_fhir
from pipelines.metadata import IngestionCheckpoint

from libs.fhir.loader import FHIRLoader, FHIRLoaderError


class GraphStore:
    def __init__(self) -> None:
        self.nodes: list[list[Any]] = []
        self.edges: list[list[Any]] = []
        self.fail_node_call: int | None = None
        self.closed = False

    async def verify_connectivity(self) -> None:
        pass

    async def run_query(self, *args: Any) -> list[Any]:
        return []

    async def load_nodes(self, nodes: list[Any]) -> int:
        self.nodes.append(nodes)
        if len(self.nodes) == self.fail_node_call:
            raise RuntimeError("interrupted batch")
        return len(nodes)

    async def load_edges(self, edges: list[Any]) -> int:
        self.edges.append(edges)
        return len(edges)

    async def close(self) -> None:
        self.closed = True


def patient_input(tmp_path: Path, count: int = 3) -> Path:
    source = tmp_path / "Patient.ndjson"
    source.write_text(
        "".join(
            json.dumps({"resourceType": "Patient", "id": f"p-{i}"}) + "\n" for i in range(count)
        )
    )
    return source


async def test_graph_retry_replays_failed_batch_and_keeps_confirmed_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = patient_input(tmp_path)
    checkpoint = tmp_path / "graph-checkpoint.json"
    first = GraphStore()
    first.fail_node_call = 2
    monkeypatch.setattr(build_graph, "Neo4jLoader", lambda **kwargs: first)
    with pytest.raises(RuntimeError, match="interrupted batch"):
        await build_graph.build_graph(
            source, "bolt://test", "user", "secret", batch_size=1, checkpoint_path=checkpoint
        )
    assert first.closed
    confirmed = json.loads(checkpoint.read_text())["completed"]
    assert set(confirmed) == {"nodes:0"}
    second = GraphStore()
    monkeypatch.setattr(build_graph, "Neo4jLoader", lambda **kwargs: second)
    result = await build_graph.build_graph(
        source, "bolt://test", "user", "secret", batch_size=1, checkpoint_path=checkpoint
    )
    assert [[node.id for node in batch] for batch in second.nodes] == [
        ["Patient/p-1"],
        ["Patient/p-2"],
    ]
    assert result["nodes_loaded"] == 3
    assert second.closed


@pytest.mark.parametrize("change", ["destination", "dataset"])
async def test_graph_checkpoint_rejects_changed_binding_before_store_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    source = patient_input(tmp_path, 1)
    checkpoint = tmp_path / "graph-checkpoint.json"
    monkeypatch.setattr(build_graph, "Neo4jLoader", lambda **kwargs: GraphStore())
    await build_graph.build_graph(
        source, "bolt://test", "user", "secret", checkpoint_path=checkpoint
    )
    if change == "dataset":
        source.write_text('{"resourceType":"Patient","id":"different"}\n')

    def forbidden(**kwargs: Any) -> None:
        pytest.fail("store opened before checkpoint binding validation")

    monkeypatch.setattr(build_graph, "Neo4jLoader", forbidden)
    with pytest.raises(ValueError, match=r"checkpoint.*binding"):
        await build_graph.build_graph(
            source,
            "bolt://other" if change == "destination" else "bolt://test",
            "user",
            "secret",
            checkpoint_path=checkpoint,
        )


class BundleStore:
    def __init__(self) -> None:
        self.uploaded: list[str] = []
        self.fail: str | None = None
        self.closed = False
        self.active = 0
        self.peak = 0
        self.pending_peak = 0
        self.cancel: str | None = None

    async def upload_bundle(self, data: dict[str, Any]) -> dict[str, Any]:
        self.uploaded.append(data["id"])
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.pending_peak = max(
            self.pending_peak,
            sum(
                task.get_coro().__name__ in {"upload", "upload_worker"}
                for task in asyncio.all_tasks()
            ),
        )
        await asyncio.sleep(0)
        self.active -= 1
        if data["id"] == self.fail:
            raise FHIRLoaderError("rejected transaction")
        if data["id"] == self.cancel:
            raise asyncio.CancelledError
        return {
            "resourceType": "Bundle",
            "type": "transaction-response",
            "entry": [{"response": {"status": "200 OK"}}],
        }

    async def close(self) -> None:
        self.closed = True


def bundle_input(tmp_path: Path, count: int = 4) -> Path:
    directory = tmp_path / "bundles"
    directory.mkdir()
    for i in range(count):
        (directory / f"p-{i}.json").write_text(
            json.dumps(
                {
                    "resourceType": "Bundle",
                    "type": "transaction",
                    "id": f"b-{i}",
                    "entry": [
                        {
                            "resource": {"resourceType": "Patient", "id": f"p-{i}"},
                            "request": {"method": "PUT", "url": f"Patient/p-{i}"},
                        }
                    ],
                }
            )
        )
    return directory


async def test_fhir_preflight_rejects_late_invalid_source_without_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = bundle_input(tmp_path)
    (directory / "z-invalid.json").write_text(
        '{"resourceType": "Bundle", "type": "transaction", "entry": [{"resource":{"resourceType":"Patient","id":"bad"},"request":{"method":"POST","url":"Patient"}}]}'
    )

    def forbidden(**kwargs: Any) -> None:
        pytest.fail("FHIR client opened before complete preflight")

    monkeypatch.setattr(load_fhir, "FHIRLoader", forbidden)
    with pytest.raises(ValueError, match="PUT"):
        await load_fhir.load_bundles(directory, "http://test/fhir")


async def test_fhir_retry_confirms_only_successful_bundles_with_bounded_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = bundle_input(tmp_path)
    checkpoint = tmp_path / "fhir-checkpoint.json"
    first = BundleStore()
    first.fail = "b-1"
    monkeypatch.setattr(load_fhir, "FHIRLoader", lambda **kwargs: first)
    result = await load_fhir.load_bundles(
        directory, "http://test/fhir", 2, checkpoint_path=checkpoint
    )
    assert result["failure"] == 1
    assert first.closed
    assert first.peak <= 2
    assert first.pending_peak <= 2
    assert "bundle:p-1.json" not in json.loads(checkpoint.read_text())["completed"]
    second = BundleStore()
    monkeypatch.setattr(load_fhir, "FHIRLoader", lambda **kwargs: second)
    result = await load_fhir.load_bundles(
        directory, "http://test/fhir", 2, checkpoint_path=checkpoint
    )
    assert result == {"total": 4, "success": 4, "failure": 0}
    assert second.uploaded == ["b-1"]
    assert second.closed


@pytest.mark.parametrize(
    "body",
    [
        {"resourceType": "OperationOutcome"},
        {
            "resourceType": "Bundle",
            "type": "transaction-response",
            "entry": [{"response": {"status": "400 Bad Request"}}],
        },
        {
            "resourceType": "Bundle",
            "type": "transaction-response",
            "entry": [{"response": {"status": "202 Accepted"}}],
        },
        {"resourceType": "Bundle", "type": "transaction-response", "entry": []},
    ],
)
async def test_fhir_http_success_with_unconfirmed_transaction_is_failure(
    body: dict[str, Any],
) -> None:
    loader = FHIRLoader("http://test/fhir")
    await loader.client.aclose()
    loader.client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(FHIRLoaderError, match="transaction"):
            await loader.upload_bundle(
                {"entry": [{"resource": {"resourceType": "Patient", "id": "p-1"}}]}
            )
    finally:
        await loader.close()


def test_checkpoint_persists_binding_before_first_store_write(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    IngestionCheckpoint(path, {"dataset": "first", "target": "store-one"})
    with pytest.raises(ValueError, match="binding mismatch"):
        IngestionCheckpoint(path, {"dataset": "first", "target": "store-two"})


async def test_fhir_cancelled_stage_replays_unconfirmed_bundle_on_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = bundle_input(tmp_path, 3)
    checkpoint = tmp_path / "interrupted.json"
    first = BundleStore()
    first.cancel = "b-1"
    monkeypatch.setattr(load_fhir, "FHIRLoader", lambda **kwargs: first)
    with pytest.raises(asyncio.CancelledError):
        await load_fhir.load_bundles(directory, "http://test/fhir", 1, checkpoint_path=checkpoint)
    assert first.closed
    assert set(json.loads(checkpoint.read_text())["completed"]) == {"bundle:p-0.json"}
    second = BundleStore()
    monkeypatch.setattr(load_fhir, "FHIRLoader", lambda **kwargs: second)
    result = await load_fhir.load_bundles(
        directory, "http://test/fhir", 1, checkpoint_path=checkpoint
    )
    assert result["failure"] == 0
    assert second.uploaded == ["b-1", "b-2"]


async def test_fhir_checkpoint_rejects_changed_destination_before_client_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = bundle_input(tmp_path, 1)
    checkpoint = tmp_path / "destination.json"
    monkeypatch.setattr(load_fhir, "FHIRLoader", lambda **kwargs: BundleStore())
    await load_fhir.load_bundles(directory, "http://test/fhir", checkpoint_path=checkpoint)

    def forbidden(**kwargs: Any) -> None:
        pytest.fail("client opened for a changed destination")

    monkeypatch.setattr(load_fhir, "FHIRLoader", forbidden)
    with pytest.raises(ValueError, match="binding mismatch"):
        await load_fhir.load_bundles(directory, "http://other/fhir", checkpoint_path=checkpoint)


async def test_fhir_invalid_bundle_metadata_is_rejected_before_any_upload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = bundle_input(tmp_path, 2)
    path = directory / "p-1.json"
    bundle = json.loads(path.read_bytes())
    bundle["id"] = "invalid/id"
    path.write_text(json.dumps(bundle))

    def forbidden(**kwargs: Any) -> None:
        pytest.fail("client opened for structurally invalid Bundle metadata")

    monkeypatch.setattr(load_fhir, "FHIRLoader", forbidden)
    with pytest.raises(ValueError, match="id"):
        await load_fhir.load_bundles(directory, "http://test/fhir")
