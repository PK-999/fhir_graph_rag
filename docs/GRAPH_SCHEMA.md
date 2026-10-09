# Knowledge Graph Schema (Flattened)

> **Current implementation (2026-10-09):** This describes the flattened graph. The registry/normalized-terminology graph-v2 design is a future proposal, not current behavior.

## Principle
As part of the RAG_on_FHIR integration, this graph implements a **Dynamically Flattened FHIR Schema**.
Every FHIR JSON resource is mapped directly into a Graph Node. All nested properties in the JSON are recursively flattened into string keys on the node (e.g. `name_0_given_0`). 

## Instance nodes
Any FHIR Resource Type is represented as a node label. Examples include:
- Patient
- Encounter
- Condition
- Observation
- MedicationRequest
- Procedure

Supported input types: Patient, Encounter, Condition, Observation, MedicationRequest, Medication, Procedure, AllergyIntolerance, Practitioner, Organization, DiagnosticReport, and ServiceRequest. Terminology concepts are not extracted as separate nodes.

## Core relationships
Relationships are derived dynamically from any `reference` field found within the FHIR JSON. The edge label is derived from the JSON key path leading up to the `reference`.

Examples:
```text
(Patient)<-[:SUBJECT]-(Encounter)
(Patient)<-[:SUBJECT]-(Condition)
(Patient)<-[:SUBJECT]-(Observation)
(Encounter)<-[:ENCOUNTER]-(Condition)
(Organization)<-[:PROVIDER]-(Encounter)
```

The current transformer uses the last nonnumeric snake_case path token, so `serviceProvider` becomes `PROVIDER` and `participant.individual` becomes `INDIVIDUAL`. Relative references and explicitly configured same-service absolute references resolve to indexed canonical targets. Bundle aliases/URNs require their original bundle scope. Contained references stay inside the source record and do not invent top-level nodes; unresolved/external/unsupported references fail preflight. Original flattened reference strings remain unchanged, with separate `*_reference_canonical` projection properties. Co-occurrence does not create `SUPPORTED_BY` edges.

## Node Properties
Properties are flattened using a recursive camelCase splitter.
For example, a FHIR Patient:
```json
{
  "name": [{"family": "Smith", "given": ["John"]}]
}
```
Becomes the following Neo4j node properties:
- `name_0_family`: "Smith"
- `name_0_given_0`: "John"

Other examples: `birthDate` → `birth_date`, `effectiveDateTime` → `effective_date_time`, and `valueQuantity.value` → `value_quantity_value`. Node `id` is canonical `ResourceType/id`. The original serialized extra fields are preserved, except top-level narrative `text`. Numeric properties stay numeric.

## Indexes
The loader creates an ID uniqueness constraint per supported resource label and indexes for patient family/given name, condition/observation/medication codes, and `Encounter.period_start`. APOC is not required.

Loading uses batches of 500 and labeled endpoint matches that use the per-resource ID constraints. `MERGE` does not remove old nodes, properties, relationships, or indexes from an earlier dataset. Input reference closure is checked before database access. Full pipeline reconciliation compares the exact graph node and reference identity sets with independently validated input; the live 100-patient demo matched 7,957 nodes and 17,130 references.

The patient overview API also creates `Summary/<Type>` nodes and `HAS_<TYPE>` edges for display. These groupings are not stored FHIR resource references; the edge inspector identifies them as display groupings.

## Query design
Graph API queries must accommodate flattened property structures.
Example: `MATCH (c:Condition)-[:SUBJECT]->(p:Patient) WHERE c.code_coding_0_code = 'xyz' RETURN p`
