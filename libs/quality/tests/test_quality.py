"""Behavioral tests for independent dataset validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from libs.quality.runner import validate_dataset
from libs.synthetic.config import EncounterConfig, GenerationConfig
from libs.synthetic.manifest import build_dataset_manifest
from libs.synthetic.runner import run_generation


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _read_ndjson(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _write_ndjson(path: Path, resources: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(resource, sort_keys=True) + "\n" for resource in resources))


@pytest.fixture
def valid_dataset(tmp_path: Path) -> Path:
    output_dir = tmp_path / "dataset"
    config = GenerationConfig(
        seed=20260830,
        patient_count=2,
        encounters=EncounterConfig(min_per_patient=10, max_per_patient=20),
        output_dir=str(output_dir),
    )
    run_generation(config)
    _write_json(output_dir / "dataset_manifest.json", build_dataset_manifest(output_dir, config))
    return output_dir


def test_schema_rule_rejects_a_resource_without_an_id(valid_dataset: Path) -> None:
    patient_file = valid_dataset / "ndjson" / "Patient.ndjson"
    resources = _read_ndjson(patient_file)
    resources.append({"resourceType": "Patient", "gender": "female"})
    _write_ndjson(patient_file, resources)

    report = validate_dataset(valid_dataset, write_report=False)

    assert report.rules["schema_validation"].status == "fail"
    assert any("id" in failure for failure in report.rules["schema_validation"].failures)


def test_schema_rule_rejects_artifact_bytes_that_do_not_match_manifest(
    valid_dataset: Path,
) -> None:
    patient_file = valid_dataset / "ndjson" / "Patient.ndjson"
    patient_file.write_bytes(patient_file.read_bytes() + b"\n")

    report = validate_dataset(valid_dataset, write_report=False)

    assert report.rules["schema_validation"].status == "fail"
    assert any(
        "checksum mismatch" in failure for failure in report.rules["schema_validation"].failures
    )


def test_duplicate_rule_rejects_a_repeated_full_resource_id(valid_dataset: Path) -> None:
    patient_file = valid_dataset / "ndjson" / "Patient.ndjson"
    resources = _read_ndjson(patient_file)
    resources.append(resources[0])
    _write_ndjson(patient_file, resources)

    report = validate_dataset(valid_dataset, write_report=False)

    assert report.rules["duplicate_ids"].status == "fail"
    assert report.rules["duplicate_ids"].failures == ["Patient/p-000001"]


def test_reference_rule_rejects_a_missing_target(valid_dataset: Path) -> None:
    encounter_file = valid_dataset / "ndjson" / "Encounter.ndjson"
    resources = _read_ndjson(encounter_file)
    resources[0]["subject"]["reference"] = "Patient/missing"
    _write_ndjson(encounter_file, resources)

    report = validate_dataset(valid_dataset, write_report=False)

    assert report.rules["reference_resolution"].status == "fail"
    assert any(
        "Patient/missing" in failure for failure in report.rules["reference_resolution"].failures
    )


def test_temporal_rule_rejects_an_encounter_ending_before_it_starts(
    valid_dataset: Path,
) -> None:
    encounter_file = valid_dataset / "ndjson" / "Encounter.ndjson"
    resources = _read_ndjson(encounter_file)
    resources[0]["period"]["end"] = "2000-01-01T00:00:00Z"
    _write_ndjson(encounter_file, resources)

    report = validate_dataset(valid_dataset, write_report=False)

    assert report.rules["temporal_consistency"].status == "fail"
    assert any(
        "end precedes start" in failure for failure in report.rules["temporal_consistency"].failures
    )


def test_coded_value_rule_rejects_coding_without_a_system(valid_dataset: Path) -> None:
    observation_file = valid_dataset / "ndjson" / "Observation.ndjson"
    resources = _read_ndjson(observation_file)
    resources[0]["code"]["coding"][0].pop("system")
    _write_ndjson(observation_file, resources)

    report = validate_dataset(valid_dataset, write_report=False)

    assert report.rules["coded_values"].status == "fail"
    assert any("system" in failure for failure in report.rules["coded_values"].failures)


def test_encounter_count_rule_rejects_a_patient_below_the_configured_minimum(
    valid_dataset: Path,
) -> None:
    bundle_file = valid_dataset / "bundles" / "p-000001.json"
    bundle = json.loads(bundle_file.read_text())
    encounters_seen = 0
    kept_entries = []
    for entry in bundle["entry"]:
        if entry["resource"]["resourceType"] == "Encounter":
            encounters_seen += 1
            if encounters_seen > 1:
                continue
        kept_entries.append(entry)
    bundle["entry"] = kept_entries
    _write_json(bundle_file, bundle)

    report = validate_dataset(valid_dataset, write_report=False)

    assert report.rules["encounter_count"].status == "fail"
    assert report.rules["encounter_count"].failures == ["Patient/p-000001 has 1 encounters"]


def test_scenario_rule_rejects_metformin_without_a_diabetes_condition(
    valid_dataset: Path,
) -> None:
    patient_file = valid_dataset / "ndjson" / "Patient.ndjson"
    patients = _read_ndjson(patient_file)
    patients.append(
        {
            "resourceType": "Patient",
            "id": "p-scenario",
            "gender": "female",
            "birthDate": "1980-01-01",
        }
    )
    _write_ndjson(patient_file, patients)

    medication_file = valid_dataset / "ndjson" / "MedicationRequest.ndjson"
    medications = _read_ndjson(medication_file) if medication_file.exists() else []
    medications.append(
        {
            "resourceType": "MedicationRequest",
            "id": "mr-without-condition",
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "coding": [
                    {
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": "6809",
                        "display": "Metformin 500 MG Oral Tablet",
                    }
                ]
            },
            "subject": {"reference": "Patient/p-scenario"},
            "authoredOn": "2026-01-01T00:00:00Z",
        }
    )
    _write_ndjson(medication_file, medications)

    report = validate_dataset(valid_dataset, write_report=False)

    assert report.rules["clinical_scenario_consistency"].status == "fail"
    assert report.rules["clinical_scenario_consistency"].failures == [
        "MedicationRequest/mr-without-condition requires Condition 44054006 for Patient/p-scenario"
    ]


def test_valid_dataset_passes_all_rules_and_reports_aggregate_counts(
    valid_dataset: Path,
) -> None:
    report = validate_dataset(valid_dataset, write_report=False)

    assert report.status == "pass"
    assert set(report.rules) == {
        "schema_validation",
        "duplicate_ids",
        "reference_resolution",
        "temporal_consistency",
        "coded_values",
        "encounter_count",
        "clinical_scenario_consistency",
        "aggregate_distribution",
    }
    assert all(result.status == "pass" for result in report.rules.values())
    assert report.rules["aggregate_distribution"].details["patient_count"] == 2


def test_quality_schema_rejects_missing_required_observation_code(valid_dataset: Path) -> None:
    observation_file = valid_dataset / "ndjson" / "Observation.ndjson"
    resources = _read_ndjson(observation_file)
    resources[0].pop("code")
    _write_ndjson(observation_file, resources)

    report = validate_dataset(valid_dataset, write_report=False)

    assert any("code" in failure for failure in report.rules["schema_validation"].failures)
    assert report.rules["schema_validation"].details["fhir_version"] == "4.0.1"


def test_quality_schema_checks_bundle_resource_payloads(valid_dataset: Path) -> None:
    bundle_file = valid_dataset / "bundles" / "shared.json"
    bundle = json.loads(bundle_file.read_text())
    bundle["entry"][0]["resource"]["active"] = "invalid_boolean"
    _write_json(bundle_file, bundle)

    report = validate_dataset(valid_dataset, write_report=False)

    assert any(
        "bundles/shared.json" in failure and "active" in failure
        for failure in report.rules["schema_validation"].failures
    )


def test_quality_reference_rule_reports_missing_contained_and_external_targets(
    valid_dataset: Path,
) -> None:
    observation_file = valid_dataset / "ndjson" / "Observation.ndjson"
    resources = _read_ndjson(observation_file)
    resources[0]["performer"] = [
        {"reference": "#missing"},
        {"reference": "https://external.example/fhir/Patient/p-000001"},
    ]
    _write_ndjson(observation_file, resources)

    report = validate_dataset(valid_dataset, write_report=False)

    failures = report.rules["reference_resolution"].failures
    assert any("#missing" in failure and "unresolved" in failure for failure in failures)
    assert any("external.example" in failure and "external" in failure for failure in failures)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_quality_report_fails_for_nonfinite_ndjson_numbers_without_changing_source(
    valid_dataset: Path, value: float
) -> None:
    observation_file = valid_dataset / "ndjson" / "Observation.ndjson"
    resources = _read_ndjson(observation_file)
    resources[0]["valueQuantity"] = {"value": value, "unit": "mg"}
    _write_ndjson(observation_file, resources)
    original = observation_file.read_bytes()

    report = validate_dataset(valid_dataset)

    assert report.status == "fail"
    assert any(
        "valueQuantity.value" in failure and "finite" in failure
        for failure in report.rules["schema_validation"].failures
    )
    assert json.loads((valid_dataset / "data_quality_summary.json").read_text())["status"] == "fail"
    assert observation_file.read_bytes() == original
