"""CLI for independently validating generated FHIR artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from libs.quality.runner import validate_dataset


def main() -> None:
    """Validate a generated dataset and return a shell-friendly status."""
    parser = argparse.ArgumentParser(description="Validate synthetic FHIR artifacts")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("artifacts"),
        help="Directory containing bundles, NDJSON, and dataset_manifest.json",
    )
    args = parser.parse_args()

    if not args.input.is_dir():
        print(f"Validation input directory does not exist: {args.input}", file=sys.stderr)
        raise SystemExit(1)

    report = validate_dataset(args.input)
    print("FHIRGraph Synthetic Dataset Validation")
    print(f"Dataset hash: {report.dataset_hash or '<missing>'}")
    for name, result in report.rules.items():
        print(f"{name}: {result.status.upper()} ({result.checked} checked)")
        for failure in result.failures[:10]:
            print(f"  - {failure}")

    print(f"Overall: {report.status.upper()}")
    raise SystemExit(0 if report.status == "pass" else 1)


if __name__ == "__main__":
    main()
