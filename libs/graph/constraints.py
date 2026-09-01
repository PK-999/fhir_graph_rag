"""Define and apply Neo4j constraints and indexes."""

import logging

from libs.graph.loader import Neo4jLoader

logger = logging.getLogger(__name__)


async def apply_constraints_and_indexes(loader: Neo4jLoader) -> None:
    """Create uniqueness constraints and indexes in Neo4j."""

    statements = [
        # Constraints
        "CREATE CONSTRAINT node_id IF NOT EXISTS FOR (n:Patient) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT enc_id IF NOT EXISTS FOR (n:Encounter) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT cond_id IF NOT EXISTS FOR (n:Condition) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT obs_id IF NOT EXISTS FOR (n:Observation) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT med_id IF NOT EXISTS FOR (n:MedicationRequest) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT prac_id IF NOT EXISTS FOR (n:Practitioner) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT org_id IF NOT EXISTS FOR (n:Organization) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT proc_id IF NOT EXISTS FOR (n:Procedure) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT diag_id IF NOT EXISTS FOR (n:DiagnosticReport) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (n:ClinicalConcept) REQUIRE n.id IS UNIQUE",

        # Indexes for fast lookup
        "CREATE INDEX pat_name IF NOT EXISTS FOR (n:Patient) ON (n.display_name)",
        "CREATE INDEX concept_code IF NOT EXISTS FOR (n:ClinicalConcept) ON (n.code)",
        "CREATE INDEX enc_start IF NOT EXISTS FOR (n:Encounter) ON (n.start)",
    ]

    for stmt in statements:
        try:
            await loader.run_query(stmt)
        except Exception as e:
            logger.error(f"Failed to execute schema statement '{stmt}': {e}")

    logger.info("Constraints and indexes applied.")
