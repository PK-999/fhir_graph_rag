"""Measure the isolated synthetic FHIR portfolio stack, preserving its volumes.

Run with the installed project interpreter: python scripts/benchmark.py
The report contains observed local measurements, not production-load estimates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import secrets
import signal
import statistics
import subprocess
import sys
import threading
import time
import uuid
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "fhirgraph-benchmark"
ISOLATED = {
    "COMPOSE_PROJECT_NAME": PROJECT,
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "55433",
    "NEO4J_URI": "bolt://localhost:57688",
    "HAPI_FHIR_URL": "http://localhost:58081/fhir",
    "API_PORT": "8110",
    "CORS_ORIGINS": "http://localhost:4110,http://127.0.0.1:4110",
    "NEXT_PUBLIC_API_URL": "http://localhost:8110/api/v1",
    "FHIRGRAPH_WEB_PORT": "4110",
    "FHIRGRAPH_API_PORT": "8110",
    "FHIRGRAPH_POSTGRES_PORT": "55433",
    "FHIRGRAPH_NEO4J_HTTP_PORT": "57475",
    "FHIRGRAPH_NEO4J_BOLT_PORT": "57688",
    "FHIRGRAPH_HAPI_PORT": "58081",
    "FHIRGRAPH_PUBLIC_API_URL": "http://localhost:8110/api/v1",
}


def read_environment(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#") and "=" in line
    )


def prepare_environment(
    output: Path, patients: int, seed: int, *, root: Path = ROOT
) -> tuple[Path, dict[str, str]]:
    """Create credentials once; never read the user's .env or alter an existing binding."""
    if patients < 1:
        raise ValueError("--patients must be positive")
    output.mkdir(parents=True, exist_ok=True)
    env_path, binding_path = output / "environment.env", output / "benchmark-binding.json"
    binding = {"schema_version": 1, "patients": patients, "seed": seed, "targets": ISOLATED}
    if env_path.is_symlink() or binding_path.is_symlink():
        raise ValueError("Benchmark binding files must not be symlinks")
    if env_path.exists() or binding_path.exists():
        if not env_path.exists() or not binding_path.exists():
            raise ValueError(
                "Incomplete benchmark binding; preserve credentials and use the original output"
            )
        saved = json.loads(binding_path.read_text())
        values = read_environment(env_path)
        digest = hashlib.sha256(env_path.read_bytes()).hexdigest()
        if saved != {**binding, "environment_sha256": digest} or any(
            values.get(key) != value for key, value in ISOLATED.items()
        ):
            raise ValueError(
                "Benchmark binding changed; reuse the original patients, seed and isolated environment"
            )
        return env_path, values
    if (
        (output / "dataset_manifest.json").exists()
        or (output / "bundles").exists()
        or (output / "ndjson").exists()
    ):
        raise ValueError("Unbound existing dataset preserved; choose a fresh benchmark output")
    content = (root / ".env.example").read_text()
    overrides = {
        **ISOLATED,
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "NEO4J_PASSWORD": secrets.token_urlsafe(32),
    }
    for key, value in overrides.items():
        pattern = rf"^{key}=.*$"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
        else:
            content += f"\n{key}={value}\n"
    descriptor = os.open(env_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write(content)
    binding_path.write_text(
        json.dumps(
            {**binding, "environment_sha256": hashlib.sha256(env_path.read_bytes()).hexdigest()},
            indent=2,
        )
        + "\n"
    )
    return env_path, read_environment(env_path)


def memory_bytes(value: str) -> int | None:
    match = re.fullmatch(r"\s*([0-9.]+)\s*([A-Za-z]+)\s*", value)
    factors = {
        "B": 1,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
        "kB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
    }
    return int(float(match[1]) * factors[match[2]]) if match and match[2] in factors else None


class MemorySampler:
    """Observe Docker working-set memory and optional cgroup RSS proxies every 5s."""

    def __init__(self, containers: list[str], env: dict[str, str], root: Path) -> None:
        self.containers, self.env, self.root = containers, env, root
        self.samples: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.started = time.monotonic()

    def sample(self) -> None:
        try:
            result = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{json .}}", *self.containers],
                env=self.env,
                cwd=self.root,
                text=True,
                capture_output=True,
                check=True,
                timeout=15,
            )
            rows = []
            for line in result.stdout.splitlines():
                data = json.loads(line)
                identifier = data["ID"]
                cgroup = subprocess.run(
                    ["docker", "exec", identifier, "cat", "/sys/fs/cgroup/memory.stat"],
                    env=self.env,
                    cwd=self.root,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=3,
                )
                fields = dict(
                    part.split() for part in cgroup.stdout.splitlines() if len(part.split()) == 2
                )
                proxy_key = (
                    "total_rss" if "total_rss" in fields else "anon" if "anon" in fields else None
                )
                rows.append(
                    {
                        "container": data["Name"],
                        "docker_memory_bytes": memory_bytes(data["MemUsage"].split("/", 1)[0]),
                        "docker_memory_display": data["MemUsage"],
                        "cpu_percent_display": data.get("CPUPerc"),
                        "cgroup_rss_proxy_bytes": int(fields[proxy_key]) if proxy_key else None,
                        "cgroup_rss_proxy_field": proxy_key,
                    }
                )
            self.samples.append(
                {"elapsed_seconds": time.monotonic() - self.started, "containers": rows}
            )
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            self.errors.append(type(exc).__name__)

    def _loop(self) -> None:
        while not self.stop_event.wait(5):
            self.sample()

    def start(self) -> None:
        self.sample()
        self.thread.start()

    def stop(self) -> dict[str, Any]:
        self.stop_event.set()
        self.thread.join(timeout=20)
        return {
            "requested_interval_seconds": 5,
            "scope": "Local sequential synthetic benchmark; Docker working-set memory, not process RSS. cgroup anon (v2) or total_rss (v1) is an RSS proxy when available.",
            "samples": self.samples,
            "sampling_errors": self.errors,
        }


def collect_audit(
    compose: list[str], env: dict[str, str], root: Path, since: datetime
) -> dict[str, Any] | None:
    # The timestamp is generated here, not taken from user input. psql runs on the
    # container's local Unix socket, keeping passwords out of arguments and JSON.
    query = f"""SELECT json_build_object('run_id',run_id,'status',status,
        'started_at',started_at,'completed_at',completed_at,
        'elapsed_seconds',EXTRACT(EPOCH FROM completed_at-started_at),
        'stage_timings',config_snapshot->'stage_timings',
        'dataset_hash',config_snapshot->>'dataset_hash')
        FROM pipeline_runs WHERE pipeline_name='full_pipeline'
        AND started_at >= '{since.isoformat()}'::timestamptz
        ORDER BY started_at DESC LIMIT 1"""
    result = subprocess.run(
        [
            *compose,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            env["POSTGRES_USER"],
            "-d",
            env["POSTGRES_DB"],
            "-At",
            "-c",
            query,
        ],
        env=env,
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
        timeout=15,
    )
    return json.loads(result.stdout) if result.stdout.strip() else None


def observe_stores_and_latency(
    output: Path, values: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected = json.loads((output / "data_quality_summary.json").read_text())["resource_counts"]
    with httpx.Client(timeout=30) as client:
        hapi = {}
        for kind in sorted(expected):
            response = client.get(f"{values['HAPI_FHIR_URL']}/{kind}", params={"_summary": "count"})
            response.raise_for_status()
            hapi[kind] = response.json()["total"]
        response = client.post(
            f"http://localhost:{values['FHIRGRAPH_NEO4J_HTTP_PORT']}/db/neo4j/tx/commit",
            auth=(values["NEO4J_USER"], values["NEO4J_PASSWORD"]),
            json={
                "statements": [
                    {"statement": "MATCH (n) RETURN labels(n)[0], count(n)"},
                    {"statement": "MATCH ()-[r]->() RETURN type(r), count(r)"},
                ]
            },
        )
        response.raise_for_status()
        graph = response.json()
        if graph.get("errors"):
            raise ValueError("Graph count query failed")
        node_counts, edge_counts = [
            dict(row["row"] for row in result["data"]) for result in graph["results"]
        ]
        if hapi != expected or node_counts != expected:
            raise ValueError("Measured store counts do not match the source")
        stores = {
            "source_counts": expected,
            "hapi_counts": hapi,
            "graph_node_counts": node_counts,
            "graph_node_count": sum(node_counts.values()),
            "graph_reference_counts": edge_counts,
            "graph_reference_count": sum(edge_counts.values()),
        }
        with (output / "ndjson" / "Patient.ndjson").open() as handle:
            patient = next(json.loads(line)["id"] for line in handle if line.strip())
        questions = [
            "List five patients",
            "Find patients with type 2 diabetes",
            "Find patients whose latest HbA1c is above 8% with active Metformin",
            "Find patients on active Metformin",
            f"Show lab history for Patient/{patient}",
        ]
        samples: list[dict[str, Any]] = []
        for index in range(20):
            question = questions[index % len(questions)]
            started = time.perf_counter()
            response = client.post(
                f"{values['FHIRGRAPH_PUBLIC_API_URL']}/assistant/query",
                json={"query": question, "use_summary_model": False},
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.raise_for_status()
            if response.json().get("status") != "answered":
                raise ValueError("Latency sample did not answer a supported question")
            samples.append({"question": question, "elapsed_ms": elapsed_ms})
    durations = sorted(sample["elapsed_ms"] for sample in samples)
    return stores, {
        "scope": "20 sequential first-page supported questions, local synthetic data, summaries disabled; not a concurrent load test",
        "sample_count": len(samples),
        "p50_ms": statistics.median(durations),
        "p95_ms": durations[math.ceil(0.95 * len(durations)) - 1],
        "percentile_method": "p50 median; p95 nearest rank",
        "samples": samples,
    }


def verify_recovery(output: Path, env: dict[str, str], root: Path) -> dict[str, Any]:
    resources = sum(
        json.loads((output / "data_quality_summary.json").read_text())["resource_counts"].values()
    )
    if resources < 3:
        raise ValueError("Recovery proof needs at least three source resources")
    checkpoint = output / ".checkpoints" / f"benchmark-recovery-{uuid.uuid4().hex}.json"
    batch_size = min(500, resources // 3)
    command = [
        sys.executable,
        "-m",
        "pipelines.build_graph",
        "--input",
        str(output / "ndjson"),
        "--batch-size",
        str(batch_size),
        "--checkpoint",
        str(checkpoint),
    ]
    log_path = output / "recovery.log"
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a") as log:
        child = subprocess.Popen(
            command, env=env, cwd=root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
        )
        try:
            deadline = time.monotonic() + 900
            while child.poll() is None:
                state = (
                    json.loads(checkpoint.read_text()) if checkpoint.exists() else {"completed": {}}
                )
                confirmed = sum(key.startswith("nodes:") for key in state["completed"])
                if confirmed >= 2:
                    child.send_signal(signal.SIGINT)
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("Graph recovery proof timed out")
                time.sleep(0.1)
            else:
                raise ValueError(
                    "Graph completed before interruption; recovery was not demonstrated"
                )
            exit_code = child.wait(timeout=30)
            if exit_code == 0:
                raise ValueError(
                    "Graph child exited successfully; interruption was not demonstrated"
                )
        finally:
            if child.poll() is None:
                child.send_signal(signal.SIGINT)
                child.wait(timeout=30)
    interrupted_state = json.loads(checkpoint.read_text())
    subprocess.run(command, env=env, cwd=root, check=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pipelines.reconcile",
            "--input",
            str(output / "data_quality_summary.json"),
            "--graph",
        ],
        env=env,
        cwd=root,
        check=True,
    )
    resumed = json.loads(checkpoint.read_text())
    if not interrupted_state["completed"].items() <= resumed["completed"].items():
        raise ValueError("Recovery lost a confirmed batch")
    return {
        "status": "pass",
        "scope": "SIGINT only the graph child, then resume and exact reconciliation; idempotent replay against the already populated graph, not an empty-store interruption",
        "batch_size": batch_size,
        "confirmed_batches_at_signal": confirmed,
        "confirmed_batches_after_interrupt": len(interrupted_state["completed"]),
        "confirmed_batches_after_resume": len(resumed["completed"]),
        "interrupted_exit_code": exit_code,
    }


def run_benchmark(
    output: Path,
    patients: int,
    seed: int,
    *,
    root: Path = ROOT,
    keep_running: bool = False,
    verify_recovery_requested: bool = False,
) -> dict[str, Any]:
    output = output.resolve()
    # A lost credential file must not be replaced when persistent project volumes exist.
    if not (output / "environment.env").exists():
        volumes = subprocess.run(
            [
                "docker",
                "volume",
                "ls",
                "-q",
                "--filter",
                f"label=com.docker.compose.project={PROJECT}",
            ],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
        if volumes.stdout.strip():
            raise ValueError(
                "Existing benchmark volumes preserved; reuse their original environment.env"
            )
    env_path, values = prepare_environment(output, patients, seed, root=root)
    env = {**os.environ, **values, "FHIRGRAPH_ENV_FILE": str(env_path)}
    compose = [
        "docker",
        "compose",
        "-p",
        PROJECT,
        "--env-file",
        str(env_path),
        "-f",
        "infra/docker-compose.yml",
        "-f",
        "infra/docker-compose.dev.yml",
    ]
    report: dict[str, Any] = {
        "schema_version": 1,
        "measured_at": datetime.now(UTC).isoformat(),
        "project": PROJECT,
        "patients_requested": patients,
        "seed": seed,
        "status": "fail",
        "wall_seconds": {},
        "pipeline_audit": None,
        "stores": None,
        "latency": None,
        "memory": None,
        "evaluation": None,
        "recovery": None,
    }
    started, phase, sampler = time.monotonic(), "compose_up", None
    audit_since: datetime | None = None
    try:
        phase_started = time.monotonic()
        subprocess.run(
            [*compose, "up", "--build", "--detach", "--wait", "--wait-timeout", "240"],
            cwd=root,
            env=env,
            check=True,
        )
        report["wall_seconds"][phase] = time.monotonic() - phase_started
        identifiers = subprocess.run(
            [*compose, "ps", "-q"], cwd=root, env=env, text=True, capture_output=True, check=True
        ).stdout.split()
        if not identifiers:
            raise ValueError("No isolated benchmark containers are running")
        sampler = MemorySampler(identifiers, env, root)
        sampler.start()
        for phase, command in [
            (
                "pipeline",
                [
                    sys.executable,
                    "-m",
                    "pipelines.run_all",
                    "--patients",
                    str(patients),
                    "--seed",
                    str(seed),
                    "--output",
                    str(output),
                ],
            ),
            (
                "evaluation",
                [
                    sys.executable,
                    "scripts/evaluate.py",
                    "--input",
                    str(output),
                    "--api-url",
                    values["FHIRGRAPH_PUBLIC_API_URL"],
                    "--output",
                    str(output / "evaluation.json"),
                ],
            ),
        ]:
            if phase == "pipeline":
                audit_since = datetime.now(UTC)
            phase_started = time.monotonic()
            subprocess.run(command, cwd=root, env=env, check=True)
            report["wall_seconds"][phase] = time.monotonic() - phase_started
            if phase == "pipeline":
                assert audit_since is not None
                report["pipeline_audit"] = collect_audit(compose, env, root, audit_since)
                if not report["pipeline_audit"] or report["pipeline_audit"]["status"] != "success":
                    raise ValueError("No successful audited pipeline run was observed")
        evaluation = json.loads((output / "evaluation.json").read_text())
        report["evaluation"] = {
            "status": evaluation["status"],
            "case_count": len(evaluation["cases"]),
            "passed_case_count": sum(case["status"] == "pass" for case in evaluation["cases"]),
            "source_checks": {
                key: evaluation.get("source_checks", {}).get(key)
                for key in ("total", "passed", "failed")
            },
        }
        if evaluation["status"] != "pass" or len(evaluation["cases"]) != 33:
            raise ValueError("The complete standard 33-case evaluation did not pass")
        phase = "store_counts_and_latency"
        phase_started = time.monotonic()
        report["stores"], report["latency"] = observe_stores_and_latency(output, values)
        if verify_recovery_requested:
            phase, phase_started = "recovery", time.monotonic()
            report["recovery"] = verify_recovery(output, env, root)
            report["wall_seconds"][phase] = time.monotonic() - phase_started
        report["status"] = "pass"
    except (
        OSError,
        ValueError,
        KeyError,
        httpx.HTTPError,
        subprocess.SubprocessError,
        KeyboardInterrupt,
    ) as exc:
        report["wall_seconds"][phase] = time.monotonic() - phase_started
        report["failure"] = {
            "phase": phase,
            "type": type(exc).__name__,
            "exit_code": getattr(exc, "returncode", None),
        }
        if audit_since and report["pipeline_audit"] is None:
            with suppress(OSError, ValueError, subprocess.SubprocessError):
                report["pipeline_audit"] = collect_audit(compose, env, root, audit_since)
    finally:
        if sampler:
            report["memory"] = sampler.stop()
        if not keep_running:
            try:
                subprocess.run([*compose, "down"], cwd=root, env=env, check=True)
            except (OSError, subprocess.SubprocessError) as exc:
                report["status"] = "fail"
                report["teardown_error"] = type(exc).__name__
        report["wall_seconds"]["overall_including_startup_and_teardown"] = (
            time.monotonic() - started
        )
        report["containers_kept_running"] = keep_running
        (output / "benchmark.json").write_text(
            json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patients", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--output", type=Path, default=Path("artifacts/release-scale"))
    parser.add_argument("--keep-running", action="store_true")
    parser.add_argument("--verify-recovery", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_benchmark(
            args.output,
            args.patients,
            args.seed,
            keep_running=args.keep_running,
            verify_recovery_requested=args.verify_recovery,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(
            f"Benchmark precondition failed ({type(exc).__name__}); existing datasets and volumes were preserved.",
            file=sys.stderr,
        )
        return 1
    print(f"Benchmark {report['status']}: {args.output / 'benchmark.json'}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
