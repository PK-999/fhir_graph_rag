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
        "CREATE CONSTRAINT allergy_id IF NOT EXISTS FOR (n:AllergyIntolerance) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT medication_id IF NOT EXISTS FOR (n:Medication) REQUIRE n.id IS UNIQUE",
        "CREATE CONSTRAINT service_req_id IF NOT EXISTS FOR (n:ServiceRequest) REQUIRE n.id IS UNIQUE",
        # The flattened schema stores the original FHIR paths in snake_case.
        "CREATE INDEX patient_family IF NOT EXISTS FOR (n:Patient) ON (n.name_0_family)",
        "CREATE INDEX patient_given IF NOT EXISTS FOR (n:Patient) ON (n.name_0_given_0)",
        "CREATE INDEX condition_code IF NOT EXISTS FOR (n:Condition) ON (n.code_coding_0_code)",
        "CREATE INDEX observation_code IF NOT EXISTS FOR (n:Observation) ON (n.code_coding_0_code)",
        "CREATE INDEX medication_request_code IF NOT EXISTS FOR (n:MedicationRequest) ON (n.medication_codeable_concept_coding_0_code)",
        "CREATE INDEX encounter_period_start IF NOT EXISTS FOR (n:Encounter) ON (n.period_start)",
    ]

    for stmt in statements:
        await loader.run_query(stmt)

    logger.info("Constraints and indexes applied.")
