# Knowledge Graph Schema (Flattened)

> **Migration notice (2026-09-01):** The schema below documents the original graph. The approved graph-v2 direction uses a typed registry, exported checksum, stable clinical projections, normalized terminology nodes, and enforced source/target relationship rules. See [`superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md`](superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md). Until graph-v2 is implemented and reconciled, this file remains descriptive rather than a claim of registry compatibility.

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

*Note: Terminology concepts are no longer extracted as separate nodes unless explicitly referenced via a standard FHIR reference URL.*

## Core relationships
Relationships are derived dynamically from any `reference` field found within the FHIR JSON. The edge label is derived from the JSON key path leading up to the `reference`.

Examples:
```text
(Patient)<-[:SUBJECT]-(Encounter)
(Patient)<-[:SUBJECT]-(Condition)
(Patient)<-[:SUBJECT]-(Observation)
(Encounter)<-[:ENCOUNTER]-(Condition)
(Organization)<-[:SERVICE_PROVIDER]-(Encounter)
```

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

## Indexes
For performance, it is recommended to index common flattened IDs and status fields.
- `Patient.id`
- `Condition.code_coding_0_code`
- `Encounter.status`

## Query design
Graph API queries must accommodate flattened property structures.
Example: `MATCH (c:Condition)-[:SUBJECT]->(p:Patient) WHERE c.code_coding_0_code = 'xyz' RETURN p`
