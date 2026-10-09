"""Executable contracts for Milestone 1 generation and validation commands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from libs.synthetic.config import GenerationConfig
from libs.synthetic.runner import run_generation

ROOT = Path(__file__).resolve().parents[1]
RULE_NAMES = (
    "schema_validation",
    "duplicate_ids",
    "reference_resolution",
    "temporal_consistency",
    "coded_values",
    "encounter_count",
    "clinical_scenario_consistency",
    "aggregate_distribution",
)


def _run_validator(output_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pipelines.validate", "--input", str(output_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validation_cli_reports_all_rules_for_a_valid_dataset(tmp_path: Path) -> None:
    run_generation(GenerationConfig(seed=9, patient_count=1, output_dir=str(tmp_path)))

    result = _run_validator(tmp_path)

    assert result.returncode == 0, result.stderr
    for rule_name in RULE_NAMES:
        assert f"{rule_name}: PASS" in result.stdout
    assert "Dataset hash:" in result.stdout


def test_generation_cli_prints_dataset_hash_and_quality_status(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pipelines.generate",
            "--patients",
            "1",
            "--seed",
            "9",
            "--output",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    manifest = json.loads((tmp_path / "dataset_manifest.json").read_text())
    assert result.returncode == 0, result.stderr
    assert f"Dataset hash: {manifest['dataset_hash']}" in result.stdout
    assert "Data quality: PASS" in result.stdout


def test_validation_cli_exits_nonzero_for_a_dangling_reference(tmp_path: Path) -> None:
    run_generation(GenerationConfig(seed=9, patient_count=1, output_dir=str(tmp_path)))
    encounter_path = tmp_path / "ndjson" / "Encounter.ndjson"
    resources = [json.loads(line) for line in encounter_path.read_text().splitlines()]
    resources[0]["subject"]["reference"] = "Patient/missing"
    encounter_path.write_text("".join(json.dumps(resource) + "\n" for resource in resources))

    result = _run_validator(tmp_path)

    assert result.returncode == 1
    assert "reference_resolution: FAIL" in result.stdout
    assert "Patient/missing" in result.stdout


def test_make_generation_targets_forward_the_output_directory() -> None:
    for target in ("generate", "validate"):
        result = subprocess.run(
            ["make", "--dry-run", target, "OUTPUT=/tmp/fhirgraph-m1-contract"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "/tmp/fhirgraph-m1-contract" in result.stdout
