"""Audit the real orchestrator while replacing its external service boundaries."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import asyncpg
import pytest
from pipelines import run_all
from pipelines.config import PipelineSettings

from libs.synthetic.config import GenerationConfig
from libs.synthetic.runner import run_generation


class MetadataConnection:
    """Capture the PostgreSQL write contract without a running database."""

    def __init__(self) -> None:
        self.runs: dict[str, dict[str, Any]] = {}
        self.quality: list[tuple[Any, ...]] = []
        self.events: list[tuple[Any, ...]] = []
        self.registered: list[str | None] = []
        self.lock_available = True
        self.closed = False
        self.writes: list[str] = []

    async def execute(self, query: str, *args: Any) -> str:
        self.writes.append(query)
        if "INSERT INTO pipeline_runs" in query:
            self.runs[args[0]] = {
                "status": "running",
                "config_snapshot": json.loads(args[1]),
                "error_message": None,
                "completed": False,
            }
        elif "UPDATE pipeline_runs" in query and "completed_at" in query:
            self.runs[args[0]].update(status=args[1], error_message=args[2], completed=True)
        elif "UPDATE pipeline_runs" in query:
            self.runs[args[0]]["config_snapshot"] = json.loads(args[1])
        return "OK"

    async def fetchval(self, query: str, *args: Any) -> bool:
        return self.lock_available

    async def fetch(self, query: str, *args: Any) -> list[dict[str, str | None]]:
        return [{"dataset_hash": value} for value in self.registered]

    async def executemany(self, query: str, args: list[tuple[Any, ...]]) -> None:
        self.writes.append(query)
        if "INSERT INTO data_quality_results" in query:
            self.quality.extend(args)
        elif "INSERT INTO ingestion_events" in query:
            self.events.extend(args)
        else:
            raise AssertionError(f"Unexpected batch: {query}")

    @asynccontextmanager
    async def transaction(self) -> Any:
        yield

    async def close(self) -> None:
        self.closed = True


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    run_generation(GenerationConfig(patient_count=2, seed=7, output_dir=str(tmp_path)))
    return tmp_path


@pytest.fixture
def metadata(monkeypatch: pytest.MonkeyPatch) -> MetadataConnection:
    connection = MetadataConnection()

    async def connect(**kwargs: Any) -> MetadataConnection:
        assert kwargs["host"] == "localhost"
        assert kwargs["port"] == 55432
        assert kwargs["password"] == "private-pg-secret"
        return connection

    monkeypatch.setattr(asyncpg, "connect", connect)
    return connection


def settings() -> PipelineSettings:
    return PipelineSettings(
        _env_file=None,
        postgres_host="localhost",
        postgres_port=55432,
        postgres_password="private-pg-secret",
        neo4j_password="private-neo4j-secret",
        hapi_fhir_url="http://username:private-hapi-secret@localhost/fhir",
    )


def test_success_persists_eight_rules_and_every_resource_for_each_confirmed_stage(
    dataset: Path, metadata: MetadataConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    modules: list[str] = []

    def step(name: str, cmd: list[str]) -> None:
        modules.append(cmd[2])
        # A successful event must never be written before its service stage returns.
        if cmd[2] == "pipelines.load_fhir":
            assert metadata.events == []
        if cmd[2] == "pipelines.build_graph":
            assert {event[4] for event in metadata.events} == {"hapi_fhir"}

    monkeypatch.setattr(run_all, "run_step", step)
    run_id = asyncio.run(run_all.run_pipeline(2, 7, dataset, settings()))

    assert modules == [
        "pipelines.generate",
        "pipelines.validate",
        "pipelines.load_fhir",
        "pipelines.build_graph",
        "pipelines.reconcile",
    ]
    run = metadata.runs[run_id]
    assert run["status"] == "success"
    assert run["completed"] is True
    assert run["error_message"] is None
    snapshot = run["config_snapshot"]
    assert snapshot["patient_count"] == 2
    assert snapshot["seed"] == 7
    assert snapshot["output"] == str(dataset)
    assert len(snapshot["dataset_hash"]) == 64
    assert set(snapshot["stages"].values()) == {"success"}
    assert "private-" not in json.dumps(snapshot)
    assert {row[1] for row in metadata.quality} == {
        "schema_validation",
        "duplicate_ids",
        "reference_resolution",
        "temporal_consistency",
        "coded_values",
        "encounter_count",
        "clinical_scenario_consistency",
        "aggregate_distribution",
    }
    assert len(metadata.quality) == 8
    assert all(row[2] is True for row in metadata.quality)
    assert all(json.loads(row[3])["status"] == "pass" for row in metadata.quality)
    resources = {
        (payload["resourceType"], payload["id"])
        for path in (dataset / "ndjson").glob("*.ndjson")
        for line in path.read_text().splitlines()
        if (payload := json.loads(line))
    }
    assert len(metadata.events) == len(resources) * 2
    for target in ("hapi_fhir", "neo4j"):
        assert {(row[1], row[2]) for row in metadata.events if row[4] == target} == resources
    assert {row[3] for row in metadata.events} == {"upserted"}
    assert metadata.closed is True


@pytest.mark.parametrize(
    ("failed_module", "confirmed_targets"),
    [("load_fhir", set()), ("build_graph", {"hapi_fhir"}), ("reconcile", {"hapi_fhir", "neo4j"})],
)
def test_failed_stage_fails_run_without_claiming_ingestion_for_that_stage(
    failed_module: str,
    confirmed_targets: set[str],
    dataset: Path,
    metadata: MetadataConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    modules: list[str] = []

    def step(name: str, cmd: list[str]) -> None:
        modules.append(cmd[2])
        if cmd[2] == f"pipelines.{failed_module}":
            raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(run_all, "run_step", step)
    with pytest.raises(subprocess.CalledProcessError):
        asyncio.run(run_all.run_pipeline(2, 7, dataset, settings()))

    run = next(iter(metadata.runs.values()))
    assert run["status"] == "failed"
    assert run["completed"] is True
    assert run["config_snapshot"]["stages"][failed_module] == "failed"
    assert modules[-1] == f"pipelines.{failed_module}"
    assert {row[4] for row in metadata.events} == confirmed_targets
    assert len(metadata.quality) == 8
    assert metadata.closed is True


@pytest.mark.parametrize("registered", ["different-dataset", None])
def test_registered_mismatch_or_unknown_hash_fails_before_any_service_mutation(
    registered: str | None,
    dataset: Path,
    metadata: MetadataConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata.registered = [registered]
    modules: list[str] = []
    monkeypatch.setattr(run_all, "run_step", lambda name, cmd: modules.append(cmd[2]))

    with pytest.raises(ValueError, match="isolated Compose project"):
        asyncio.run(run_all.run_pipeline(2, 7, dataset, settings()))

    assert modules == ["pipelines.generate", "pipelines.validate"]
    assert metadata.events == []
    assert next(iter(metadata.runs.values()))["status"] == "failed"


def test_same_registered_dataset_can_run_again(
    dataset: Path, metadata: MetadataConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata.registered = [
        json.loads((dataset / "dataset_manifest.json").read_text())["dataset_hash"]
    ]
    monkeypatch.setattr(run_all, "run_step", lambda name, cmd: None)

    run_id = asyncio.run(run_all.run_pipeline(2, 7, dataset, settings()))

    assert metadata.runs[run_id]["status"] == "success"


def test_rejected_dataset_does_not_claim_ingestion_started(
    dataset: Path, metadata: MetadataConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata.registered = ["different-dataset"]
    monkeypatch.setattr(run_all, "run_step", lambda name, cmd: None)
    with pytest.raises(ValueError, match="isolated Compose project"):
        asyncio.run(run_all.run_pipeline(2, 7, dataset, settings()))
    run = next(iter(metadata.runs.values()))
    assert run["config_snapshot"]["stages"]["load_fhir"] == "blocked"
    assert metadata.events == []


def test_failed_validation_still_persists_all_quality_failures(
    dataset: Path, metadata: MetadataConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    report_path = dataset / "data_quality_summary.json"
    report = json.loads(report_path.read_text())
    report["status"] = "fail"
    report["rules"]["schema_validation"].update(status="fail", failures=["invalid observation"])
    report_path.write_text(json.dumps(report))

    def step(name: str, cmd: list[str]) -> None:
        if cmd[2] == "pipelines.validate":
            raise subprocess.CalledProcessError(1, cmd)
        assert cmd[2] == "pipelines.generate"

    monkeypatch.setattr(run_all, "run_step", step)
    with pytest.raises(subprocess.CalledProcessError):
        asyncio.run(run_all.run_pipeline(2, 7, dataset, settings()))

    assert len(metadata.quality) == 8
    failed = [row for row in metadata.quality if not row[2]]
    assert len(failed) == 1
    assert json.loads(failed[0][3])["failures"] == ["invalid observation"]
    assert metadata.events == []


def test_concurrent_pipeline_is_rejected_before_generation(
    dataset: Path, metadata: MetadataConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata.lock_available = False
    modules: list[str] = []
    monkeypatch.setattr(run_all, "run_step", lambda name, cmd: modules.append(cmd[2]))

    with pytest.raises(RuntimeError, match="already running"):
        asyncio.run(run_all.run_pipeline(2, 7, dataset, settings()))

    assert modules == []
    assert metadata.closed is True


def test_missing_postgres_credentials_fails_before_generation(
    dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    modules: list[str] = []
    monkeypatch.setattr(run_all, "run_step", lambda name, cmd: modules.append(cmd[2]))
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        asyncio.run(
            run_all.run_pipeline(
                2, 7, dataset, PipelineSettings(_env_file=None, postgres_password=None)
            )
        )
    assert modules == []


def test_provenance_records_exact_artifact_location_hash_and_confirmed_destination(
    dataset: Path, metadata: MetadataConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(run_all, "run_step", lambda name, cmd: None)
    run_id = asyncio.run(run_all.run_pipeline(2, 7, dataset, settings()))
    dataset_hash = json.loads((dataset / "dataset_manifest.json").read_text())["dataset_hash"]
    for row in metadata.events:
        # Existing first five fields remain the legacy event contract.
        (
            _,
            resource_type,
            resource_id,
            _,
            target,
            canonical_id,
            artifact,
            location,
            source_line,
            content_hash,
            recorded_dataset,
            version,
            destination,
            confirmed_stage,
        ) = row
        assert canonical_id == f"{resource_type}/{resource_id}"
        if target == "neo4j":
            payload = json.loads((dataset / artifact).read_text().splitlines()[source_line - 1])
            assert location == f"line:{source_line}"
            assert confirmed_stage == "build_graph"
        else:
            payload = json.loads((dataset / artifact).read_text())["entry"][
                int(location.split(":")[1])
            ]["resource"]
            assert source_line is None
            assert confirmed_stage == "load_fhir"
        assert payload["id"] == resource_id
        assert (
            content_hash
            == hashlib.sha256(
                json.dumps(
                    payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest()
        )
        assert recorded_dataset == dataset_hash
        assert version
        assert "private-" not in destination
    assert all(row[0] == run_id for row in metadata.events)
    assert any("ADD COLUMN IF NOT EXISTS" in query for query in metadata.writes)


def test_changed_source_after_service_success_cannot_claim_wrong_provenance(
    dataset: Path, metadata: MetadataConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    def step(name: str, cmd: list[str]) -> None:
        if cmd[2] == "pipelines.load_fhir":
            source = next((dataset / "bundles").glob("*.json"))
            bundle = json.loads(source.read_bytes())
            bundle["entry"][0]["resource"]["meta"] = {"source": "changed-after-upload"}
            source.write_text(json.dumps(bundle))

    monkeypatch.setattr(run_all, "run_step", step)
    with pytest.raises(ValueError, match=r"artifact.*manifest"):
        asyncio.run(run_all.run_pipeline(2, 7, dataset, settings()))
    assert metadata.events == []
