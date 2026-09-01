"""Pipeline to build the Neo4j Knowledge Graph from generated FHIR data."""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from libs.fhir.models.base import FHIRResource
from libs.graph.constraints import apply_constraints_and_indexes
from libs.graph.loader import Neo4jLoader
from libs.graph.schema import GraphEdge, GraphNode
from libs.graph.transformer import FHIRToGraphTransformer

from libs.fhir.models.patient import Patient
from libs.fhir.models.encounter import Encounter
from libs.fhir.models.condition import Condition
from libs.fhir.models.observation import Observation
from libs.fhir.models.medication import MedicationRequest
from libs.fhir.models.procedure import Procedure, DiagnosticReport
from libs.fhir.models.allergy_intolerance import AllergyIntolerance
from libs.fhir.models.practitioner import Practitioner, Organization
from libs.fhir.models.base import FHIRResource

RESOURCE_MODELS = {
    "Patient": Patient,
    "Encounter": Encounter,
    "Condition": Condition,
    "Observation": Observation,
    "MedicationRequest": MedicationRequest,
    "Procedure": Procedure,
    "AllergyIntolerance": AllergyIntolerance,
    "Practitioner": Practitioner,
    "Organization": Organization,
    "DiagnosticReport": DiagnosticReport
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def build_graph(ndjson_path: Path, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> dict:
    """Read FHIR NDJSON, transform to Graph canonical models, and load into Neo4j."""

    logger.info("Initializing Neo4j loader and schema...")
    loader = Neo4jLoader(uri=neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        await loader.verify_connectivity()
    except Exception as e:
        logger.error(f"Could not connect to Neo4j at {neo4j_uri}: {e}")
        return {"success": False, "error": str(e)}

    await apply_constraints_and_indexes(loader)

    transformer = FHIRToGraphTransformer()

    # We will accumulate nodes and edges and batch them
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    # Gather all NDJSON files in the input path
    ndjson_files = list(ndjson_path.glob("*.ndjson")) if ndjson_path.is_dir() else [ndjson_path]
    
    if not ndjson_files:
        logger.error(f"No NDJSON files found in {ndjson_path}")
        return {"success": False, "error": "No NDJSON files found"}

    for file_path in ndjson_files:
        logger.info(f"Reading NDJSON from {file_path}...")
        with file_path.open() as f:
            for line in f:
                if not line.strip():
                    continue

                data = json.loads(line)
                res_type = data.get("resourceType")
                model_cls = RESOURCE_MODELS.get(res_type, FHIRResource)
                
                try:
                    resource = model_cls.model_validate(data)
                    n, edge_list = transformer.transform(resource)
                    nodes.extend(n)
                    edges.extend(edge_list)
                except Exception as e:
                    logger.warning(f"Failed to parse or transform {res_type}: {e}")

    logger.info(f"Transformed into {len(nodes)} total nodes and {len(edges)} total edges.")

    # Batch loading
    logger.info("Loading nodes into Neo4j...")
    nodes_loaded = await loader.load_nodes(nodes)

    logger.info("Loading edges into Neo4j...")
    edges_loaded = await loader.load_edges(edges)

    # 5.4 - Derived semantic edges: SUPPORTED_BY (Condition -> Observation)
    # Simple semantic derivation for the demo:
    # Conditions and Observations linked to the same Encounter.
    derived_query = """
    MATCH (c:Condition)-[:DURING_ENCOUNTER]->(e:Encounter)<-[:DURING_ENCOUNTER]-(o:Observation)
    MERGE (c)-[r:SUPPORTED_BY]->(o)
    SET r.derivation_rule = 'co_occurring_encounter'
    RETURN count(r) as c
    """
    logger.info("Computing derived semantic edges...")
    try:
        result = await loader.run_query(derived_query)
        derived_edges = result[0]["c"] if result else 0
        logger.info(f"Derived {derived_edges} SUPPORTED_BY edges.")
    except Exception as e:
        logger.error(f"Error computing derived edges: {e}")
        derived_edges = 0

    await loader.close()

    return {
        "success": True,
        "nodes_loaded": nodes_loaded,
        "edges_loaded": edges_loaded + derived_edges,
        "derived_edges": derived_edges
    }


def main() -> None:
    """Run graph builder from command line."""
    parser = argparse.ArgumentParser(description="Build Neo4j Knowledge Graph from FHIR NDJSON")
    parser.add_argument("--input", type=str, default="artifacts/ndjson", help="Path to FHIR NDJSON directory or file")
    parser.add_argument("--uri", type=str, default="bolt://localhost:7687", help="Neo4j Bolt URI")
    parser.add_argument("--user", type=str, default="neo4j", help="Neo4j username")
    parser.add_argument("--password", type=str, default="neo4j_dev_password", help="Neo4j password")
    args = parser.parse_args()

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
        results = asyncio.run(build_graph(input_file, args.uri, args.user, args.password))
    except KeyboardInterrupt:
        print("\nGraph build interrupted by user.")
        sys.exit(1)

    elapsed = time.time() - start

    if results.get("success"):
        print(f"\n✅ Graph build complete in {elapsed:.1f}s")
        print(f"   Nodes loaded: {results['nodes_loaded']}")
        print(f"   Edges loaded: {results['edges_loaded']} (including {results['derived_edges']} derived)")
    else:
        print(f"\n❌ Graph build failed: {results.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
