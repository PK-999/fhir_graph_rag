"""CLI for synthetic FHIR data generation."""

from __future__ import annotations

import argparse
import sys
import time


def main() -> None:
    """Run synthetic data generation from command line."""
    parser = argparse.ArgumentParser(description="Generate synthetic FHIR R4 data")
    parser.add_argument("--patients", type=int, default=20, help="Number of patients to generate")
    parser.add_argument(
        "--seed", type=int, default=20260830, help="Random seed for reproducibility"
    )
    parser.add_argument("--output", type=str, default="artifacts", help="Output directory")
    parser.add_argument("--min-encounters", type=int, default=10, help="Min encounters per patient")
    parser.add_argument("--max-encounters", type=int, default=20, help="Max encounters per patient")
    parser.add_argument("--history-years", type=int, default=5, help="Years of history to generate")
    args = parser.parse_args()

    from libs.synthetic.config import EncounterConfig, GenerationConfig
    from libs.synthetic.runner import run_generation

    config = GenerationConfig(
        seed=args.seed,
        patient_count=args.patients,
        encounters=EncounterConfig(
            min_per_patient=args.min_encounters,
            max_per_patient=args.max_encounters,
        ),
        history_years=args.history_years,
        output_dir=args.output,
    )

    print("🏥 FHIRGraph Synthetic Data Generator")
    print(f"   Patients: {config.patient_count}")
    print(
        f"   Encounters: {config.encounters.min_per_patient}–{config.encounters.max_per_patient} per patient"
    )
    print(f"   Seed: {config.seed}")
    print(f"   Output: {config.output_dir}")
    print()

    start = time.time()
    try:
        summary = run_generation(config)
    except ValueError as e:
        print(f"❌ Generation failed: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start

    print(f"✅ Generation complete in {elapsed:.1f}s")
    print(f"   Patients: {summary['patient_count']}")
    print(f"   Encounters: {summary['encounter_count']}")
    print(f"   Total resources: {summary['total_resources']}")
    print(f"   Dangling references: {summary['dangling_references']}")
    print(f"   Dataset hash: {summary['dataset_hash']}")
    print(f"   Data quality: {summary['status'].upper()}")
    print(
        f"   Encounters/patient: min={summary['encounters_per_patient']['min']}, "
        f"max={summary['encounters_per_patient']['max']}, "
        f"mean={summary['encounters_per_patient']['mean']}"
    )
    print()
    print("Resource counts:")
    for rtype, count in sorted(summary["resource_counts"].items()):
        print(f"   {rtype}: {count}")


if __name__ == "__main__":
    main()
