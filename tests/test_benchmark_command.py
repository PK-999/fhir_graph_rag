"""Benchmark isolation and real report derivation with external boundaries replaced."""

from __future__ import annotations

import importlib
import json
import signal
import subprocess
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]


def module() -> Any:
    try:
        return importlib.import_module("scripts.benchmark")
    except ModuleNotFoundError:
        pytest.fail("The isolated benchmark helper is missing")


def project(tmp_path: Path) -> Path:
    (tmp_path / ".env.example").write_text((ROOT / ".env.example").read_text())
    (tmp_path / ".env").write_text(
        "POSTGRES_PASSWORD=user-private-original\nCOMPOSE_PROJECT_NAME=user-demo\n"
    )
    return tmp_path


def test_environment_uses_isolated_ports_and_preserves_original_and_new_credentials(
    tmp_path: Path,
) -> None:
    benchmark = module()
    root = project(tmp_path)
    output = root / "artifacts" / "scale"
    original = (root / ".env").read_bytes()
    env_path, values = benchmark.prepare_environment(output, 1000, 7, root=root)
    assert values["COMPOSE_PROJECT_NAME"] == "fhirgraph-benchmark"
    assert values["FHIRGRAPH_WEB_PORT"] == "4110"
    assert values["FHIRGRAPH_API_PORT"] == "8110"
    assert values["POSTGRES_PORT"] == "55433"
    assert values["NEO4J_URI"] == "bolt://localhost:57688"
    assert values["FHIRGRAPH_NEO4J_HTTP_PORT"] == "57475"
    assert values["HAPI_FHIR_URL"] == "http://localhost:58081/fhir"
    assert values["POSTGRES_PASSWORD"] != "change-this-postgres-password"
    assert values["POSTGRES_PASSWORD"] != values["NEO4J_PASSWORD"]
    assert env_path.stat().st_mode & 0o777 == 0o600
    private = env_path.read_bytes()
    benchmark.prepare_environment(output, 1000, 7, root=root)
    assert env_path.read_bytes() == private
    assert (root / ".env").read_bytes() == original


@pytest.mark.parametrize("change", ["patients", "seed", "target"])
def test_existing_binding_rejects_changed_dataset_or_destination_without_overwriting(
    tmp_path: Path, change: str
) -> None:
    benchmark = module()
    root = project(tmp_path)
    output = root / "scale"
    env_path, _ = benchmark.prepare_environment(output, 1000, 7, root=root)
    if change == "target":
        env_path.write_text(
            env_path.read_text().replace("FHIRGRAPH_HAPI_PORT=58081", "FHIRGRAPH_HAPI_PORT=58080")
        )
    private = env_path.read_bytes()
    with pytest.raises(ValueError, match=r"binding|isolated"):
        benchmark.prepare_environment(
            output, 1001 if change == "patients" else 1000, 8 if change == "seed" else 7, root=root
        )
    assert env_path.read_bytes() == private


def test_existing_unbound_dataset_is_preserved(tmp_path: Path) -> None:
    benchmark = module()
    root = project(tmp_path)
    output = root / "scale"
    output.mkdir()
    manifest = output / "dataset_manifest.json"
    manifest.write_text('{"dataset_hash":"original"}')
    with pytest.raises(ValueError, match=r"unbound|Unbound"):
        benchmark.prepare_environment(output, 1000, 7, root=root)
    assert manifest.read_text() == '{"dataset_hash":"original"}'
    assert not (output / "environment.env").exists()


def external_boundaries(
    benchmark: Any, output: Path, monkeypatch: pytest.MonkeyPatch, *, fail_pipeline: bool = False
) -> list[list[str]]:
    commands: list[list[str]] = []

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(cmd)
        stdout = ""
        if cmd[:3] == ["docker", "volume", "ls"]:
            stdout = ""
        elif cmd[:2] == ["docker", "info"]:
            stdout = json.dumps({"MemTotal": 8589934592, "NCPU": 4, "ServerVersion": "test-engine"})
        elif "ps" in cmd:
            stdout = "container-one\n"
        elif cmd[:2] == ["docker", "stats"]:
            stdout = json.dumps(
                {
                    "ID": "container-one",
                    "Name": "fhirgraph-benchmark-api-1",
                    "MemUsage": "128MiB / 8GiB",
                    "CPUPerc": "1.2%",
                }
            )
        elif cmd[:2] == ["docker", "exec"]:
            stdout = "anon 104857600\nfile 41943040\n"
        elif "psql" in cmd:
            stdout = json.dumps(
                {
                    "run_id": "real-audit-id",
                    "status": "success",
                    "started_at": "2026-10-09T01:00:00Z",
                    "completed_at": "2026-10-09T01:00:09Z",
                    "elapsed_seconds": 9,
                    "stage_timings": {"generate": {"elapsed_seconds": 2, "status": "success"}},
                    "dataset_hash": "a" * 64,
                }
            )
        elif "pipelines.run_all" in cmd:
            if fail_pipeline:
                raise subprocess.CalledProcessError(
                    2, cmd, stderr="private-error-must-not-be-published"
                )
            assert kwargs["env"]["COMPOSE_PROJECT_NAME"] == "fhirgraph-benchmark"
            assert kwargs["env"]["POSTGRES_PORT"] == "55433"
            assert kwargs["env"]["FHIRGRAPH_ENV_FILE"] == str(output / "environment.env")
            (output / "dataset_manifest.json").write_text(json.dumps({"dataset_hash": "a" * 64}))
            (output / "data_quality_summary.json").write_text(
                json.dumps({"resource_counts": {"Patient": 2, "Observation": 1}, "status": "pass"})
            )
            ndjson = output / "ndjson"
            ndjson.mkdir()
            (ndjson / "Patient.ndjson").write_text('{"resourceType":"Patient","id":"p-000001"}\n')
        elif "scripts/evaluate.py" in cmd:
            (output / "evaluation.json").write_text(
                json.dumps(
                    {
                        "status": "pass",
                        "cases": [{"name": f"case-{i}", "status": "pass"} for i in range(33)],
                        "source_checks": {"total": 3, "passed": 3, "failed": 0},
                    }
                )
            )
        return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")

    original_client = httpx.Client

    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/assistant/query"):
            assert json.loads(request.content)["use_summary_model"] is False
            return httpx.Response(200, json={"status": "answered"})
        if request.url.path.endswith("/tx/commit"):
            return httpx.Response(
                200,
                json={
                    "errors": [],
                    "results": [
                        {"data": [{"row": ["Patient", 2]}, {"row": ["Observation", 1]}]},
                        {"data": [{"row": ["SUBJECT", 1]}]},
                    ],
                },
            )
        return httpx.Response(200, json={"total": 2 if request.url.path.endswith("Patient") else 1})

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    monkeypatch.setattr(
        benchmark.httpx,
        "Client",
        lambda **kwargs: original_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    return commands


def test_benchmark_derives_sanitized_metrics_and_stops_without_removing_volumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark = module()
    root = project(tmp_path)
    output = root / "scale"
    monkeypatch.setenv("COMPOSE_PROJECT_NAME", "original-demo")
    monkeypatch.setenv("POSTGRES_PORT", "55432")
    commands = external_boundaries(benchmark, output, monkeypatch)
    report = benchmark.run_benchmark(output, 2, 7, root=root)
    assert report["status"] == "pass"
    assert report["pipeline_audit"]["run_id"] == "real-audit-id"
    assert report["pipeline_audit"]["elapsed_seconds"] == 9
    assert report["evaluation"]["case_count"] == 33
    assert report["stores"]["hapi_counts"] == {"Patient": 2, "Observation": 1}
    assert report["stores"]["graph_node_count"] == 3
    assert report["latency"]["sample_count"] == 20
    assert len(report["latency"]["samples"]) == 20
    sample = report["memory"]["samples"][0]["containers"][0]
    assert sample["docker_memory_bytes"] == 134217728
    assert sample["cgroup_rss_proxy_bytes"] == 104857600
    public = (output / "benchmark.json").read_text()
    values = benchmark.read_environment(output / "environment.env")
    assert values["POSTGRES_PASSWORD"] not in public
    assert values["NEO4J_PASSWORD"] not in public
    assert "user-private-original" not in public
    assert any(cmd[-1] == "down" for cmd in commands)
    assert all("--volumes" not in cmd for cmd in commands)
    assert all("--case-id" not in cmd for cmd in commands)
    assert all(
        "--env-file" not in cmd or str(output / "environment.env") in cmd for cmd in commands
    )


def test_failure_report_has_no_fake_metrics_or_private_error_and_still_preserves_volumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark = module()
    root = project(tmp_path)
    output = root / "scale"
    commands = external_boundaries(benchmark, output, monkeypatch, fail_pipeline=True)
    report = benchmark.run_benchmark(output, 2, 7, root=root)
    assert report["status"] == "fail"
    assert report["latency"] is None
    assert report["stores"] is None
    assert report["failure"]["phase"] == "pipeline"
    assert report["wall_seconds"]["pipeline"] >= 0
    assert "private-error" not in (output / "benchmark.json").read_text()
    assert any(cmd[-1] == "down" for cmd in commands)


def test_keep_running_skips_teardown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    benchmark = module()
    root = project(tmp_path)
    output = root / "scale"
    commands = external_boundaries(benchmark, output, monkeypatch)
    benchmark.run_benchmark(output, 2, 7, root=root, keep_running=True)
    assert all(cmd[-1] != "down" for cmd in commands)


def test_missing_credentials_with_existing_volumes_stops_before_creating_or_starting_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark = module()
    root = project(tmp_path)
    commands = []

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 0, stdout="fhirgraph-benchmark_pg_data\n", stderr=""
        )

    monkeypatch.setattr(benchmark.subprocess, "run", run)
    output = root / "scale"
    with pytest.raises(ValueError, match="volumes preserved"):
        benchmark.run_benchmark(output, 1000, 7, root=root)
    assert not (output / "environment.env").exists()
    assert len(commands) == 1
    assert commands[0][:3] == ["docker", "volume", "ls"]


def test_recovery_signals_only_graph_child_after_confirmations_and_reconciles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark = module()
    output = tmp_path / "scale"
    output.mkdir()
    (output / "data_quality_summary.json").write_text('{"resource_counts":{"Patient":1500}}')
    commands: list[list[str]] = []
    signals: list[int] = []
    original = output / ".checkpoints" / "build_graph.json"
    original.parent.mkdir()
    original.write_text('{"completed":{"existing-proof":"old-hash"}}')
    active_checkpoint: Path | None = None

    class Child:
        returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def send_signal(self, number: int) -> None:
            signals.append(number)
            self.returncode = 1

        def wait(self, timeout: float) -> int:
            assert self.returncode is not None
            return self.returncode

    def popen(cmd: list[str], **kwargs: Any) -> Child:
        nonlocal active_checkpoint
        commands.append(cmd)
        assert kwargs["start_new_session"] is True
        active_checkpoint = Path(cmd[cmd.index("--checkpoint") + 1])
        assert active_checkpoint.parent == output / ".checkpoints"
        assert active_checkpoint != original
        assert not active_checkpoint.exists()
        active_checkpoint.write_text('{"completed":{"nodes:0":"one","nodes:1":"two"}}')
        return Child()

    def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(cmd)
        if "pipelines.build_graph" in cmd:
            assert active_checkpoint is not None
            active_checkpoint.write_text(
                '{"completed":{"nodes:0":"one","nodes:1":"two","nodes:2":"three","edges:0":"four"}}'
            )
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(benchmark.subprocess, "Popen", popen)
    monkeypatch.setattr(benchmark.subprocess, "run", run)
    proof = benchmark.verify_recovery(output, {}, tmp_path)
    assert signals == [signal.SIGINT]
    assert proof["status"] == "pass"
    assert proof["confirmed_batches_at_signal"] == 2
    assert proof["confirmed_batches_after_resume"] == 4
    assert "already populated graph" in proof["scope"]
    assert original.read_text() == '{"completed":{"existing-proof":"old-hash"}}'
    assert commands[0] == commands[1]
    assert commands[2][2] == "pipelines.reconcile"
    assert "--graph" in commands[2]


def test_finished_graph_is_not_misrepresented_as_interrupted_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    benchmark = module()
    (tmp_path / "data_quality_summary.json").write_text('{"resource_counts":{"Patient":1500}}')

    class FinishedChild:
        def poll(self) -> int:
            return 0

    monkeypatch.setattr(benchmark.subprocess, "Popen", lambda *args, **kwargs: FinishedChild())
    with pytest.raises(ValueError, match="completed before interruption"):
        benchmark.verify_recovery(tmp_path, {}, tmp_path)
