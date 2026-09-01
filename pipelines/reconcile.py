"""CLI for reconciling FHIR server counts against generated data quality summary."""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from libs.fhir.loader import FHIRLoader

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def reconcile_counts(dq_summary_path: Path, fhir_url: str) -> bool:
    """Reconcile HAPI FHIR resource counts with the data quality summary."""
    with dq_summary_path.open() as f:
        dq_summary = json.load(f)

    expected_counts = dq_summary.get("resource_counts", {})
    if not expected_counts:
        logger.error("No resource_counts found in data quality summary.")
        return False

    loader = FHIRLoader(base_url=fhir_url)

    all_match = True
    print(f"{'Resource Type':<25} | {'Expected':<10} | {'Actual':<10} | {'Status':<10}")
    print("-" * 62)

    for resource_type, expected_count in sorted(expected_counts.items()):
        try:
            actual_count = await loader.get_resource_count(resource_type)
            match = actual_count == expected_count
            status = "✅ MATCH" if match else "❌ MISMATCH"

            print(f"{resource_type:<25} | {expected_count:<10} | {actual_count:<10} | {status}")

            if not match:
                all_match = False
        except Exception as e:
            logger.error(f"Error querying {resource_type}: {e}")
            all_match = False

    await loader.close()
    return all_match


def main() -> None:
    """Run count reconciliation from command line."""
    parser = argparse.ArgumentParser(description="Reconcile FHIR server resource counts with expected totals")
    parser.add_argument("--input", type=str, default="artifacts/data_quality_summary.json", help="Path to DQ summary JSON")
    parser.add_argument("--url", type=str, default="http://localhost:8080/fhir", help="FHIR Server base URL")
    args = parser.parse_args()

    input_file = Path(args.input)
    if not input_file.exists() or not input_file.is_file():
        logger.error(f"DQ summary file does not exist: {input_file}")
        sys.exit(1)

    print("⚖️ FHIRGraph Count Reconciliation")
    print(f"   Expected: {input_file}")
    print(f"   Target:   {args.url}")
    print()

    start = time.time()

    try:
        success = asyncio.run(reconcile_counts(input_file, args.url))
    except KeyboardInterrupt:
        print("\nReconciliation interrupted by user.")
        sys.exit(1)

    elapsed = time.time() - start
    print(f"\nReconciliation completed in {elapsed:.1f}s")

    if success:
        print("\n🎉 SUCCESS: All resource counts match exactly!")
        sys.exit(0)
    else:
        print("\n⚠️ FAILURE: Mismatches found between expected and actual counts.")
        sys.exit(1)


if __name__ == "__main__":
    main()
