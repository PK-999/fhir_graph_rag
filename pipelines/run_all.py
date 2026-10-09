"""Run and audit the complete single-dataset portfolio pipeline."""

import argparse
import asyncio
import subprocess
import sys
import time
import uuid
from pathlib import Path

import asyncpg

from pipelines.config import PipelineSettings
from pipelines.metadata import RunAudit, target_identity


def run_step(name: str, cmd: list[str]) -> None:
    print(f"\nStarting: {name}", flush=True)
    subprocess.run(cmd, check=True)


async def run_pipeline(patients: int, seed: int, output: Path, config: PipelineSettings) -> str:
    if not config.postgres_password:
        raise ValueError("Set POSTGRES_PASSWORD in .env or the environment")
    connection = await asyncpg.connect(
        host=config.postgres_host,
        port=config.postgres_port,
        database=config.postgres_db,
        user=config.postgres_user,
        password=config.postgres_password,
        timeout=10,
    )
    run_id = str(uuid.uuid4())
    audit = RunAudit(
        connection,
        run_id,
        {
            "patient_count": patients,
            "seed": seed,
            "output": str(output),
            "stages": {},
            "targets": {
                "hapi_fhir": target_identity(config.hapi_fhir_url),
                "neo4j": target_identity(config.neo4j_uri, config.neo4j_user),
            },
        },
    )
    started = False
    stage = "setup"
    stage_started = False
    try:
        if not await connection.fetchval("SELECT pg_try_advisory_lock(764320104)"):
            raise RuntimeError("Another pipeline is already running")
        await audit.start()
        started = True
        for stage, name, options in [
            (
                "generate",
                "Generate Synthetic Data",
                ["--patients", str(patients), "--seed", str(seed), "--output", str(output)],
            ),
            ("validate", "Validate Dataset", ["--input", str(output)]),
            ("load_fhir", "Load FHIR to HAPI", ["--input", str(output / "bundles")]),
            ("build_graph", "Build Knowledge Graph", ["--input", str(output / "ndjson")]),
            (
                "reconcile",
                "Reconcile Stores",
                ["--input", str(output / "data_quality_summary.json"), "--graph"],
            ),
        ]:
            stage_started = False
            if stage == "load_fhir":
                await audit.guard_dataset()
            await audit.stage(stage, "running")
            stage_started = True
            try:
                run_step(name, [sys.executable, "-m", f"pipelines.{stage}", *options])
            finally:
                if stage == "validate":
                    await audit.quality(output)
            if stage in ("load_fhir", "build_graph"):
                await audit.ingestion(output, "hapi_fhir" if stage == "load_fhir" else "neo4j")
            await audit.stage(stage, "success")
        await audit.finish("success")
        return run_id
    except BaseException as exc:
        if started:
            await audit.stage(stage, "failed" if stage_started else "blocked")
            await audit.finish("failed", f"{stage} failed: {type(exc).__name__}")
        raise
    finally:
        await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patients", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    start = time.monotonic()
    try:
        run_id = asyncio.run(
            run_pipeline(args.patients, args.seed, args.output, PipelineSettings())
        )
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Pipeline failed: {exc}\n")
    print(f"Pipeline {run_id} succeeded in {time.monotonic() - start:.1f}s")


if __name__ == "__main__":
    main()
