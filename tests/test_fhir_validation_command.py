"""The standalone structural validation command reads original artifact bytes."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from libs.synthetic.config import GenerationConfig
from libs.synthetic.runner import run_generation


def test_structural_command_reports_pinned_schema_and_leaves_source_bytes_unchanged(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "dataset"
    run_generation(GenerationConfig(patient_count=1, output_dir=str(output_dir)))
    before = (output_dir / "ndjson" / "Patient.ndjson").read_bytes()

    result = subprocess.run(
        [sys.executable, "-m", "pipelines.validate_fhir", "--input", str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((output_dir / "fhir_validation_report.json").read_text())
    assert report["status"] == "pass"
    assert report["schema"]["fhir_version"] == "4.0.1"
    assert "full FHIR conformance" in " ".join(report["schema"]["limitations"])
    assert (output_dir / "ndjson" / "Patient.ndjson").read_bytes() == before


def test_structural_command_rejects_invalid_serialized_enums(tmp_path: Path) -> None:
    output_dir = tmp_path / "dataset"
    run_generation(GenerationConfig(patient_count=1, output_dir=str(output_dir)))
    path = output_dir / "ndjson" / "Patient.ndjson"
    patient = json.loads(path.read_text())
    patient["gender"] = "not-valid"
    path.write_text(json.dumps(patient) + "\n")

    result = subprocess.run(
        [sys.executable, "-m", "pipelines.validate_fhir", "--input", str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    report = json.loads((output_dir / "fhir_validation_report.json").read_text())
    assert report["status"] == "fail"
    assert any("gender" in failure for failure in report["rules"]["schema_validation"]["failures"])


def test_structural_command_missing_input_returns_a_concrete_diagnostic(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pipelines.validate_fhir", "--input", str(tmp_path / "missing")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "does not exist" in result.stderr


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_structural_command_writes_failure_report_for_nonstandard_json_numbers(
    tmp_path: Path, constant: str
) -> None:
    output_dir = tmp_path / "dataset"
    run_generation(GenerationConfig(patient_count=1, output_dir=str(output_dir)))
    path = output_dir / "ndjson" / "Observation.ndjson"
    source = (
        '{"resourceType":"Observation","id":"o-nonfinite","status":"final",'
        f'"code":{{"text":"example"}},"valueQuantity":{{"value":{constant}}}}}\n'
    )
    path.write_text(source)

    result = subprocess.run(
        [sys.executable, "-m", "pipelines.validate_fhir", "--input", str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    report = json.loads((output_dir / "fhir_validation_report.json").read_text())
    assert report["status"] == "fail"
    assert any(
        "valueQuantity.value" in failure and "finite" in failure
        for failure in report["rules"]["schema_validation"]["failures"]
    )
    assert path.read_text() == source
