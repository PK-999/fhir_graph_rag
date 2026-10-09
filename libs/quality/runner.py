"""Orchestrate all serialized-dataset quality rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from libs.quality.models import ValidationReport
from libs.quality.reader import load_dataset
from libs.quality.rules import RULES


def _summary_from_rules(rules: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    aggregate = rules["aggregate_distribution"].details
    encounter = rules["encounter_count"].details
    validation_failures = [
        failure
        for result in rules.values()
        if result.status == "fail"
        for failure in result.failures
    ]
    return {
        "seed": manifest.get("generation", {}).get("seed"),
        "patient_count": aggregate["patient_count"],
        "encounter_count": aggregate["resource_counts"].get("Encounter", 0),
        "resource_counts": aggregate["resource_counts"],
        "total_resources": aggregate["total_resources"],
        "dangling_references": len(rules["reference_resolution"].failures),
        "duplicate_ids": len(rules["duplicate_ids"].failures),
        "reference_count": rules["reference_resolution"].checked,
        "encounters_per_patient": {
            "min": encounter["minimum"],
            "max": encounter["maximum"],
            "mean": encounter["mean"],
        },
        "validation_failures": validation_failures,
    }


def validate_dataset(
    output_dir: Path, *, write_report: bool = True, service_base_url: str | None = None
) -> ValidationReport:
    """Validate emitted artifacts and optionally write the deterministic report."""
    snapshot = load_dataset(output_dir, service_base_url=service_base_url)
    rule_results = {result.name: result for rule in RULES for result in (rule(snapshot),)}
    status: Literal["pass", "fail"] = (
        "pass" if all(result.status == "pass" for result in rule_results.values()) else "fail"
    )
    dataset_hash = snapshot.manifest.get("dataset_hash", "")
    report = ValidationReport(
        status=status,
        dataset_hash=dataset_hash if isinstance(dataset_hash, str) else "",
        rules=rule_results,
        summary=_summary_from_rules(rule_results, snapshot.manifest),
    )
    if write_report:
        report_path = output_dir / "data_quality_summary.json"
        report_path.write_text(json.dumps(report_payload(report), indent=2, sort_keys=True) + "\n")
    return report


def report_payload(report: ValidationReport) -> dict[str, Any]:
    """Flatten compatibility summary fields into the persisted DQ payload."""
    return {
        **report.summary,
        "status": report.status,
        "dataset_hash": report.dataset_hash,
        "rules": {name: result.model_dump(mode="json") for name, result in report.rules.items()},
    }
