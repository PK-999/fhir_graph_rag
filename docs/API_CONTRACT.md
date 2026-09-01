# API Contract

> **Migration notice (2026-09-01):** The endpoints below describe the original contract. The approved finish-line API adds generated frontend types, cursor pagination, dataset/provenance metadata, stable problem details, truthful readiness, and typed assistant plans/evidence. See [`superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md`](superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md). Contract changes are not considered shipped until implementation and integration gates pass.

Base prefix: `/api/v1`

## Health
`GET /health`

## Dashboard
`GET /dashboard/summary`

## Patients
`GET /patients?q=&condition=&limit=&cursor=`

`GET /patients/{patient_id}`

`GET /patients/{patient_id}/timeline`

`GET /patients/{patient_id}/graph?depth=2&from=&to=`

`GET /patients/{patient_id}/fhir`

`GET /patients/{patient_id}/provenance`

## Graph
`GET /graph/node/{resource_type}/{resource_id}`

`GET /graph/neighbors/{resource_type}/{resource_id}?relationship=&depth=1`

`POST /graph/path`

## Cohorts
`POST /cohorts/query`

Example:
```json
{
  "filters": [
    {"field":"condition","op":"equals","value":"type-2-diabetes"},
    {"field":"age","op":"gt","value":50},
    {"field":"observation.hba1c.latest","op":"gt","value":8}
  ],
  "limit": 100
}
```

## Data quality
`GET /data-quality/summary`

`GET /data-quality/issues`

`GET /pipeline-runs`

## AI
`POST /assistant/query`

Input:
```json
{"question":"Show patients with diabetes and latest HbA1c above 8"}
```

Response:
```json
{
  "answer":"...",
  "evidence":[
    {"resource_type":"Patient","id":"p-000123"},
    {"resource_type":"Observation","id":"p-000123-o-0012"}
  ],
  "query_plan":{"template":"diabetes_hba1c_cohort"},
  "warnings":[]
}
```

## AI safeguards
- read-only access
- allowlisted query templates preferred
- generated Cypher must pass AST/string validation
- reject CREATE/MERGE/DELETE/SET/REMOVE/DROP/CALL unless explicitly approved internal operation
- enforce LIMIT
- evidence IDs must come from query results
