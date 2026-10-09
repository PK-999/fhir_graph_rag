"""Audit durations use elapsed time and distinguish unstarted stages."""

import json
from types import SimpleNamespace
from typing import Any

import pytest
from pipelines import metadata
from pipelines.metadata import RunAudit, canonical_sha256


class MetadataConnection:
    def __init__(self) -> None:
        self.snapshot: dict[str, Any] = {}

    async def execute(self, query: str, *args: Any) -> None:
        if len(args) == 2:
            self.snapshot = json.loads(args[1])


async def test_audit_records_elapsed_stage_time(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = iter([100.0, 102.5])
    monkeypatch.setattr(
        metadata, "time", SimpleNamespace(monotonic=lambda: next(ticks)), raising=False
    )
    connection = MetadataConnection()
    audit = RunAudit(connection, "timed-run", {"stages": {}})
    await audit.start()
    await audit.stage("generate", "running")
    await audit.stage("generate", "success")
    await audit.stage("load_fhir", "blocked")
    timings = connection.snapshot["stage_timings"]
    assert timings["generate"]["elapsed_seconds"] == 2.5
    assert timings["generate"]["status"] == "success"
    assert "elapsed_seconds" not in timings["load_fhir"]


async def test_running_snapshot_refresh_preserves_stage_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = [100.0]
    monkeypatch.setattr(
        metadata, "time", SimpleNamespace(monotonic=lambda: clock[0]), raising=False
    )
    connection = MetadataConnection()
    audit = RunAudit(connection, "timed-run", {"stages": {}})
    await audit.stage("validate", "running")
    started_at = connection.snapshot["stage_timings"]["validate"]["started_at"]
    clock[0] = 110.0
    # Persisting the quality report refreshes the running audit snapshot.
    await audit.stage("validate", "running")
    clock[0] = 112.0
    await audit.stage("validate", "success")
    timing = connection.snapshot["stage_timings"]["validate"]
    assert timing["elapsed_seconds"] == 12.0
    assert timing["started_at"] == started_at


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_artifact_hash_rejects_non_json_numbers(value: float) -> None:
    with pytest.raises(ValueError):
        canonical_sha256({"value": value})
