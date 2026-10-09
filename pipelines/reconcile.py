"""CLI for reconciling FHIR server counts against generated data quality summary."""

import argparse
import asyncio
import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import cast

from neo4j import AsyncGraphDatabase

from libs.fhir.loader import FHIRLoader
from libs.graph.schema import GraphEdge
from pipelines.config import PipelineSettings

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


async def reconcile_graph(ndjson_path: Path, config: PipelineSettings) -> bool:
    """Compare exact graph identity/reference sets, including unexpected leftovers."""
    from pipelines.build_graph import _graph_batches, _read_graph_input

    if not config.neo4j_password:
        raise ValueError("Set NEO4J_PASSWORD before graph reconciliation")
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as spool:
        index, _, _ = _read_graph_input(ndjson_path, spool)
        expected_nodes = index.known_ids
        expected_edges = {
            (edge.source_id, edge.type, edge.target_id)
            for batch in _graph_batches(spool, index, "edges", 500)
            for edge in cast("list[GraphEdge]", batch)
        }
    driver = AsyncGraphDatabase.driver(
        config.neo4j_uri, auth=(config.neo4j_user, config.neo4j_password)
    )
    try:
        async with driver.session() as session:
            result = await session.run("MATCH (n) RETURN n.id AS id")
            actual_nodes = {record["id"] async for record in result}
            result = await session.run(
                "MATCH (s)-[r]->(t) RETURN s.id AS source, type(r) AS kind, t.id AS target"
            )
            actual_edges = {
                (record["source"], record["kind"], record["target"]) async for record in result
            }
        match = expected_nodes == actual_nodes and expected_edges == actual_edges
        print(
            f"Graph reconciliation: {len(actual_nodes)} nodes, {len(actual_edges)} references; {'MATCH' if match else 'MISMATCH'}"
        )
        if not match:
            print(
                f"Missing/extra nodes: {len(expected_nodes - actual_nodes)}/{len(actual_nodes - expected_nodes)}; missing/extra references: {len(expected_edges - actual_edges)}/{len(actual_edges - expected_edges)}"
            )
        return match
    finally:
        await driver.close()


def main() -> None:
    """Run count reconciliation from command line."""
    parser = argparse.ArgumentParser(
        description="Reconcile FHIR server resource counts with expected totals"
    )
    config = PipelineSettings()
    parser.add_argument(
        "--input",
        type=str,
        default="artifacts/data_quality_summary.json",
        help="Path to DQ summary JSON",
    )
    parser.add_argument(
        "--url", type=str, default=config.hapi_fhir_url, help="FHIR Server base URL"
    )
    parser.add_argument(
        "--graph", action="store_true", help="Also reconcile exact graph IDs and references"
    )
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
        if args.graph:
            success = asyncio.run(reconcile_graph(input_file.parent / "ndjson", config)) and success
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
