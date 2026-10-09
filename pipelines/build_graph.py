"""Pipeline to build the Neo4j Knowledge Graph from generated FHIR data."""

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TextIO, cast

from libs.fhir.models.allergy_intolerance import AllergyIntolerance
from libs.fhir.models.base import FHIRResource
from libs.fhir.models.condition import Condition
from libs.fhir.models.encounter import Encounter
from libs.fhir.models.medication import Medication, MedicationRequest
from libs.fhir.models.observation import Observation
from libs.fhir.models.patient import Patient
from libs.fhir.models.practitioner import Organization, Practitioner
from libs.fhir.models.procedure import DiagnosticReport, Procedure, ServiceRequest
from libs.fhir.references import ReferenceIndex, iter_references, resource_key
from libs.fhir.validation import validate_resource
from libs.graph.constraints import apply_constraints_and_indexes
from libs.graph.loader import Neo4jLoader
from libs.graph.schema import GraphEdge, GraphNode
from libs.graph.transformer import FHIRToGraphTransformer
from pipelines.config import PipelineSettings
from pipelines.metadata import (
    TRANSFORMER_VERSION,
    IngestionCheckpoint,
    canonical_sha256,
    dataset_identity,
    default_checkpoint,
    target_identity,
)

RESOURCE_MODELS: dict[str, type[FHIRResource]] = {
    "Patient": Patient,
    "Encounter": Encounter,
    "Condition": Condition,
    "Observation": Observation,
    "MedicationRequest": MedicationRequest,
    "Medication": Medication,
    "Procedure": Procedure,
    "AllergyIntolerance": AllergyIntolerance,
    "Practitioner": Practitioner,
    "Organization": Organization,
    "DiagnosticReport": DiagnosticReport,
    "ServiceRequest": ServiceRequest,
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _records(spool: TextIO) -> Iterator[dict[str, Any]]:
    spool.seek(0)
    for line in spool:
        yield json.loads(line)


def _transform(
    data: dict[str, Any], index: ReferenceIndex
) -> tuple[list[GraphNode], list[GraphEdge]]:
    model = RESOURCE_MODELS[data["resourceType"]].model_validate(data)
    return FHIRToGraphTransformer().transform(model, source=data, reference_index=index)


def _read_graph_input(
    ndjson_path: Path, spool: TextIO, service_base_url: str | None = None
) -> tuple[ReferenceIndex, str, dict[str, str]]:
    """Snapshot source to disk, retaining only a compact identity/reference index in memory."""
    files = sorted(ndjson_path.glob("*.ndjson")) if ndjson_path.is_dir() else [ndjson_path]
    if not files:
        raise ValueError(f"No NDJSON files found in {ndjson_path}")
    index = ReferenceIndex(service_base_url=service_base_url)
    digest = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    count = 0
    for path in files:
        digest.update(path.name.encode())
        digest.update(b"\0")
        file_digest = hashlib.sha256()
        with path.open("rb") as handle:
            for number, raw in enumerate(handle, 1):
                digest.update(raw)
                file_digest.update(raw)
                if not raw.strip():
                    continue
                location = f"{path}:{number}"
                try:
                    data = json.loads(raw)
                    if not isinstance(data, dict):
                        raise ValueError("expected a JSON object")
                    resource_type = data.get("resourceType")
                    model = (
                        RESOURCE_MODELS.get(resource_type)
                        if isinstance(resource_type, str)
                        else None
                    )
                    if model is None:
                        raise ValueError(
                            f"unsupported or missing resourceType: {data.get('resourceType')!r}"
                        )
                    key = resource_key(data)
                    if key is None:
                        raise ValueError(f"Invalid FHIR resource ID: {data.get('id')!r}")
                    if key in index.known_ids:
                        raise ValueError(f"duplicate resource ID: {key}")
                    issues = validate_resource(data)
                    if issues:
                        raise ValueError(
                            "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
                        )
                    model.model_validate(data)
                    index.add(data)
                    spool.write(json.dumps({"data": data, "source": location}) + "\n")
                    count += 1
                except Exception as exc:
                    raise ValueError(f"{location}: {exc}") from exc
        digest.update(b"\0")
        file_hashes[path.name] = file_digest.hexdigest()
    if not count:
        raise ValueError(f"No FHIR resources found in {ndjson_path}")
    # This completes reference/model/transform validation before opening a database.
    # Nodes and edges from this check are immediately discarded, never collected.
    for record in _records(spool):
        data = record["data"]
        try:
            for occurrence in iter_references(data):
                resolution = index.resolve(occurrence.reference, data, path=occurrence.path)
                if resolution.status not in ("resolved", "contained"):
                    raise ValueError(
                        f"{occurrence.path}: reference {occurrence.reference!r}: {resolution.diagnostic}"
                    )
            _transform(data, index)
        except Exception as exc:
            raise ValueError(f"{record['source']}: {exc}") from exc
    return index, digest.hexdigest(), file_hashes


def _graph_batches(
    spool: TextIO, index: ReferenceIndex, stage: str, batch_size: int
) -> Iterator[list[GraphNode | GraphEdge]]:
    batch: list[GraphNode | GraphEdge] = []
    for record in _records(spool):
        nodes, edges = _transform(record["data"], index)
        for item in nodes if stage == "nodes" else edges:
            batch.append(item)
            if len(batch) == batch_size:
                yield batch
                batch = []
    if batch:
        yield batch
    elif stage == "edges":
        # Preserve schema/load failure detection even for a resource-only graph.
        yield []


async def build_graph(
    ndjson_path: Path,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    *,
    batch_size: int = 500,
    checkpoint_path: Path | None = None,
    resume: bool = True,
    service_base_url: str | None = None,
) -> dict[str, Any]:
    """Preflight the entire immutable input snapshot, then stream idempotent graph batches."""
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as spool:
        index, digest, file_hashes = _read_graph_input(ndjson_path, spool, service_base_url)
        checkpoint = IngestionCheckpoint(
            checkpoint_path or default_checkpoint(ndjson_path, "build_graph"),
            {
                "stage": "build_graph",
                "target": target_identity(neo4j_uri, neo4j_user),
                "dataset_hash": dataset_identity(ndjson_path, digest, file_hashes),
                "source_digest": digest,
                "transformer_version": TRANSFORMER_VERSION,
                "batch_size": batch_size,
                "reference_service": service_base_url,
            },
            resume=resume,
        )
        loader = Neo4jLoader(uri=neo4j_uri, auth=(neo4j_user, neo4j_password))
        counts = {"nodes": 0, "edges": 0}
        try:
            await loader.verify_connectivity()
            await apply_constraints_and_indexes(loader)
            # All nodes must exist before any cross-batch reference edge is written.
            for stage in ("nodes", "edges"):
                for number, batch in enumerate(_graph_batches(spool, index, stage, batch_size)):
                    batch_digest = canonical_sha256(
                        [item.model_dump(mode="json") for item in batch]
                    )
                    key = f"{stage}:{number}"
                    if not checkpoint.confirmed(key, batch_digest):
                        loaded = await (
                            loader.load_nodes(cast("list[GraphNode]", batch))
                            if stage == "nodes"
                            else loader.load_edges(cast("list[GraphEdge]", batch))
                        )
                        if loaded != len(batch):
                            raise ValueError("Not every graph input was loaded")
                        checkpoint.confirm(key, batch_digest)
                    counts[stage] += len(batch)
            return {
                "success": True,
                "nodes_loaded": counts["nodes"],
                "edges_loaded": counts["edges"],
                "derived_edges": 0,
            }
        finally:
            await loader.close()


def main() -> None:
    """Run graph builder from command line."""
    parser = argparse.ArgumentParser(description="Build Neo4j Knowledge Graph from FHIR NDJSON")
    config = PipelineSettings()
    parser.add_argument(
        "--input",
        type=str,
        default="artifacts/ndjson",
        help="Path to FHIR NDJSON directory or file",
    )
    parser.add_argument("--uri", type=str, default=config.neo4j_uri, help="Neo4j Bolt URI")
    parser.add_argument("--user", type=str, default=config.neo4j_user, help="Neo4j username")
    parser.add_argument(
        "--password", type=str, default=config.neo4j_password, help="Neo4j password"
    )
    parser.add_argument(
        "--batch-size", type=int, default=500, help="Maximum graph objects per confirmed batch"
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="Checkpoint path (default: output/.checkpoints/build_graph.json, outside source artifacts)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Replay the same bound dataset using idempotent MERGE",
    )
    parser.add_argument(
        "--service-base-url",
        help="FHIR service base for explicitly resolving same-service absolute references",
    )
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    if not args.password:
        parser.error("Set NEO4J_PASSWORD in .env or the environment, or pass --password")

    input_file = Path(args.input)
    if not input_file.exists():
        logger.error(f"Input file does not exist: {input_file}")
        sys.exit(1)

    print("🕸️ FHIRGraph Neo4j Builder")
    print(f"   Source: {input_file}")
    print(f"   Target: {args.uri}")
    print()

    start = time.time()

    try:
        options: dict[str, Any] = {}
        if args.batch_size != 500:
            options["batch_size"] = args.batch_size
        if args.checkpoint:
            options["checkpoint_path"] = args.checkpoint
        if args.no_resume:
            options["resume"] = False
        if args.service_base_url:
            options["service_base_url"] = args.service_base_url
        results = asyncio.run(
            build_graph(input_file, args.uri, args.user, args.password, **options)
        )
    except ValueError as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        print("\nGraph build interrupted by user.")
        sys.exit(1)

    elapsed = time.time() - start

    if results.get("success"):
        print(f"\n✅ Graph build complete in {elapsed:.1f}s")
        print(f"   Nodes loaded: {results['nodes_loaded']}")
        print(
            f"   Edges loaded: {results['edges_loaded']} (including {results['derived_edges']} derived)"
        )
    else:
        print(f"\n❌ Graph build failed: {results.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
