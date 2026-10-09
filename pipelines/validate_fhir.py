"""Offline pinned FHIR R4 structural and dataset reference validation command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from libs.fhir.validation import structural_validation_metadata
from libs.quality.reader import load_dataset
from libs.quality.rules import duplicate_ids, reference_resolution, schema_validation


def main() -> None:
    """Validate original serialized artifacts and write a scoped conformance report."""
    parser = argparse.ArgumentParser(
        description="Validate pinned official FHIR R4 structural schema"
    )
    parser.add_argument(
        "--input", type=Path, default=Path("artifacts"), help="Generated dataset directory"
    )
    parser.add_argument(
        "--service-base-url", help="Explicit FHIR service base for same-service absolute references"
    )
    parser.add_argument(
        "--report", type=Path, help="Report location; defaults to INPUT/fhir_validation_report.json"
    )
    args = parser.parse_args()
    if not args.input.is_dir():
        print(f"Validation input directory does not exist: {args.input}", file=sys.stderr)
        raise SystemExit(1)
    try:
        snapshot = load_dataset(args.input, service_base_url=args.service_base_url)
        results = [
            rule(snapshot) for rule in (schema_validation, duplicate_ids, reference_resolution)
        ]
        status = "pass" if all(result.status == "pass" for result in results) else "fail"
        payload = {
            "status": status,
            "schema": structural_validation_metadata(),
            "dataset_hash": snapshot.manifest.get("dataset_hash", ""),
            "resources_checked": len(snapshot.records),
            "bundles_checked": len(snapshot.bundle_records),
            "rules": {result.name: result.model_dump(mode="json") for result in results},
        }
        report_path = args.report or args.input / "fhir_validation_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError) as exc:
        print(f"FHIR structural validation could not complete: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(
        "FHIR R4 4.0.1 structural validation (not full profile/invariant/terminology conformance)"
    )
    for result in results:
        print(f"{result.name}: {result.status.upper()} ({result.checked} resources checked)")
        for failure in result.failures[:10]:
            print(f"  - {failure}")
    print(f"Report: {report_path}")
    print(f"Overall: {status.upper()}")
    raise SystemExit(0 if status == "pass" else 1)


if __name__ == "__main__":
    main()
