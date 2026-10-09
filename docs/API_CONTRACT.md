# Current API contract

Updated 2026-10-09. Base prefix: `/api/v1`. These routes describe the implementation. Typed plans, bounded offset pagination for assistant results, and exact FHIR resource retrieval are available. Resource provenance and optional local-model fact selection are available.

## Routes

| Method | Path | Behavior |
|---|---|---|
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | Neo4j, PostgreSQL, and HAPI readiness; 503 if degraded |
| GET | `/health` | Compatibility readiness route |
| GET | `/dashboard/summary` | Graph population and resource counts |
| GET | `/patients` | `q`, `gender`, `dob_start`, `dob_end`, `page`, `limit`, `sort`, `order` |
| GET | `/patients/{patient_id}` | Patient details, counts, bounded clinical lists |
| GET | `/patients/{patient_id}/timeline` | Combined encounters and clinical event timeline |
| GET | `/patients/{patient_id}/summary-graph` | Patient node and resource-type bundles |
| GET | `/graph/neighbors/{node_id}` | Canonical node ID, bounded `depth` |
| GET | `/graph/explore/{node_id}` | Expansion options by connected resource type |
| GET | `/graph/explore/{node_id}/expand` | Required `relationship` and `target_label`, bounded `limit` |
| GET | `/cohorts/conditions` | Condition code/display search using `q`, bounded `limit` |
| POST | `/cohorts/query` | Condition and age filters |
| GET | `/data-quality/summary` | Latest persisted PostgreSQL run/results, if present |
| GET | `/lineage` | Static business-to-FHIR mappings from PostgreSQL |
| GET | `/lineage/resources/{resource_type}/{resource_id}` | Up to 100 confirmed artifact-to-store ingestion events; unavailable for legacy/missing evidence |
| POST | `/assistant/query` | Strict plans, owned parameterized retrieval, exact source evidence, or abstention |
| GET | `/resources/{resource_type}/{resource_id}` | Bounded exact HAPI FHIR resource proxy |

Patient routes accept bare IDs such as `p-000001` and explicit canonical forms such as `/patients/Patient/p-000001/timeline`. Graph paths accept canonical IDs such as `Patient/p-000001`. Patient projections retain UI fields `name`, `birthDate`, and `counts`, while the underlying graph uses flattened snake_case properties.

## Cohorts

```json
{"conditions": ["44054006"], "min_age": 18, "max_age": 80}
```

`condition_codes` is an accepted alias for `conditions`. At most 10 nonblank conditions of at most 20 characters each are accepted. Age ranges must be ordered; ages use birthday-based date calculations. Results contain `query`, `count`, and `patients`, limited to 100 rows. The count is the size of the returned list.

## Assistant

```json
{"query": "Find patients whose latest HbA1c is above 8% with active Metformin"}
```

`query` contains 1–2,000 characters. An optional `plan` uses the strict schema in OpenAPI: intent `patient_list`, `condition_cohort`, `latest_lab_medication`, `patient_history`, `medication_cohort`, or `patient_lab_history`; limit 1–100 (default20); and the fields required by that intent. Latest-lab plans require `lab_code`, `medication_code`, numeric `threshold`, `unit`, and optionally `comparison` (gt/gte/lt/lte, defaultgt) and `condition_code`. History and lab history require a canonical `patient_id`; lab history optionally narrows `lab_code`. Medication cohorts require `medication_code` and optionally `condition_code`. Extra or incompatible fields return422.

The default parser supports the advertised examples without a model. `use_model: true` enables experimental local-model planning only when its strict plan agrees with the complete supported deterministic meaning. Unsupported questions remain abstained. Invalid model plans abstain; provider failure returns502. Missing graph connectivity or retrieval failure returns503.

The response contains `status` (`answered` or `abstained`), `answer`, `results`, `result_count`, `evidence`, `plan`, `planner`, `cypher`, `parameters`, and `pagination`. An unsupported question returns200 with `abstained`, empty results/evidence, no query, and null pagination. An answered zero-match query remains `answered`. Result counts describe the returned page, not total counts. Each patient/resource evidence entry includes an exact source path:

```json
{
  "type": "Observation",
  "id": "Observation/p-000044-o-0096",
  "patient_id": "Patient/p-000044",
  "label": "Hemoglobin A1c",
  "source_url": "/resources/Observation/p-000044-o-0096",
  "facts": {
    "Observation.code.coding[0].code": "4548-4",
    "Observation.subject.reference": "Patient/p-000044",
    "Observation.valueQuantity.value": 9.1,
    "Observation.valueQuantity.unit": "%"
  }
}
```

`source_url` is relative to `/api/v1`. The proxy accepts supported resource types and valid FHIR IDs, checks returned resource identity, uses a five-second upstream timeout, and maps missing sources to404 and failed/invalid sources to502. Clinical retrieval uses parameterized queries with a30-second database timeout. The app never executes model-written Cypher.

Latest observations are selected before filtering values/units. Recorded medication status `active` does not establish adherence. Facts and bounded answers are deterministic; the optional model's interpretation remains experimental. The mapping catalog is static; pipeline audit records explain runs and confirmed stages, not clinical causal provenance.

## Assistant pagination

Request `offset` is a strict integer from0 through `2^63 - 101`, default0. It is separate from the clinical plan; models cannot put pagination fields into `QueryPlan`. The plan's `limit` is the page size. Every owned template sorts deterministically, skips the offset, and fetches one lookahead row. The lookahead is excluded from results, answers, and citations.

```json
{"offset": 0, "limit": 20, "has_more": true, "next_offset": 20}
```

This is the response's `pagination` object. To continue, submit the same question and returned `plan` with `offset` equal to `next_offset`. `has_more:false` and `next_offset:null` identify the final page, including an exactly full final page. Cohorts and patient lists sort by canonical Patient ID; history sorts by its recorded date and resource ID. There is no separate total-count query or server cursor.

The frontend appends rows and deduplicates evidence by canonical resource ID. A failed or invalid page retains prior results and the retry offset. Paging uses the registered local dataset; it does not provide a snapshot under manual edits or concurrent ingestion. The separate `/cohorts/query` endpoint and patient detail projections remain bounded and do not use this assistant pagination contract.

## Recorded patient history

```json
{"query": "Show history for Patient/p-000001"}
```

History retrieves directly linked patient resources through standard `subject.reference` fields and `AllergyIntolerance.patient.reference`. Duplicate links do not duplicate records. It returns up to the requested page size (default20, maximum100 per request), with further pages available. Results are ordered by recorded date descending, then canonical resource ID ascending; undated entries follow dated entries. Both latest-lab and history sorts compare UTC instants with nanosecond precision before applying ID ties.

Each history row includes `resource_id`, `resource_type`, `event_at`, and `event_field` alongside available code, status, and observation/medication fields. Date fields are Observation/DiagnosticReport `effectiveDateTime`, Encounter `period.start`, Condition `onsetDateTime` with `recordedDate` fallback, MedicationRequest/ServiceRequest `authoredOn`, Procedure `performedDateTime`, and AllergyIntolerance `recordedDate`. These fields have different meanings; prescription authorship is not evidence of medication administration. Exact dates and patient associations appear in the source citations.

A known patient with no directly linked history resources retains a patient row and citation on the first page, with a null `resource_id`; an unknown patient yields zero rows and evidence. Both have `has_more:false`. Subsequent offsets beyond a result set return zero rows and evidence. The independent evaluator traverses complete results and has no 100-patient cap.

These routes serve a local synthetic-data demo without authentication. `/docs` and `/openapi.json` provide executable schemas.

## Optional cited fact selection

`use_summary_model:true` is opt-in and returns `claims`, `summary`, and `summary_metadata` alongside deterministic results. Local Ollama selects from a bounded set of retrieved candidate facts. Exact resource IDs, paths, JSON value types and values are validated; wording is rendered by the application. This check is against retrieved graph evidence. The independent evaluator separately checks exact live HAPI fields; callers can inspect source JSON to detect store drift.

Metadata status is `not_requested`, `no_evidence`, `validated`, `rejected`, or `unavailable`, with requested/model/claim_count fields. Rejected or unavailable selection retains retrieval. Pagination preserves the summary option; selected facts shown after continuation describe the latest page.

## Resource provenance

The provenance route validates supported types and FHIR IDs. It returns resource_id, status, hash_scope and events ordered newest first, bounded to 100. Events include source_artifact/location/line, canonical content_sha256, dataset_hash, run_id/status, transformer_version, sanitized target_identity, confirmed_stage and ingestion timestamp. Hashes cover canonical artifact JSON before server metadata. They do not claim a live-store hash probe. Older schemas/rows return unavailable with no invented evidence; the pipeline performs idempotent schema migration.
