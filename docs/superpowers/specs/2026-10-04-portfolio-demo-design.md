# FHIRGraph portfolio demo

The user wants an end-to-end personal portfolio project using mock healthcare data: synthetic FHIR R4 resources become an explicit-reference graph and support grounded retrieval and answers. The existing generator, graph browser, patient timeline, cohort API, and local Ollama installation are retained.

## Demo contract

Run the application locally with Docker, generate a deterministic dataset, validate it, upload it to HAPI FHIR, build Neo4j, reconcile counts, and record the run and quality results in PostgreSQL. A visitor can inspect patient histories and graph references, ask supported clinical questions, and open the exact FHIR resources supporting each result. A documented evaluation compares live API answers against independent NDJSON-derived expected results.

## Question engine

Replace arbitrary model-written Cypher with validated typed plans and application-owned parameterized queries. Supported intents are `patient_list`, `condition_cohort`, `latest_lab_medication`, and `patient_history`. Demo terminology is explicit: SNOMED type 2 diabetes `44054006`, LOINC HbA1c `4548-4`, RxNorm Metformin `6809`. A deterministic parser handles advertised examples; optional local Ollama planning handles variations through the same strict schema. Unsupported or ambiguous requests return `status: abstained` and no graph query, evidence, or clinical advice.

`POST /assistant/query` accepts `query` and optional validated `plan`. Responses retain `answer`, `results`, `result_count`, `evidence`, and `cypher`, adding `status` (`answered` or `abstained`), `plan`, `parameters`, and `planner`. Evidence objects contain `type`, canonical `id`, `label`, `patient_id`, `source_url` (the API resource URL), and `facts` with source FHIR field paths. Resource evidence can include numeric value, unit, timestamp, clinical code, and medication status. Answers describe retrieved observations; they do not diagnose or recommend treatment. Result limits are explicit and never described as population totals.

Latest-lab retrieval selects the latest final/amended/corrected observation per patient before applying the numeric threshold. Timestamp ties use descending canonical resource ID. A missing/non-numeric latest value or a mismatched unit must not fall back to an older qualifying value. Active medication means the recorded MedicationRequest status is `active`, not inferred dispensing or adherence. Values and facts link to `GET /resources/{resource_type}/{resource_id}`, a bounded HAPI proxy accepting supported resource types and valid FHIR IDs.

## Recorded runs

The full pipeline persists a unique run ID, dataset hash, non-secret configuration, start/end/status, all eight independent quality-rule results, and per-resource ingestion events only after the relevant stage succeeds. Failures update the run status and do not claim successful ingestion. A different dataset must fail before changing services when a prior successful dataset is registered, with instructions for a fresh isolated Compose project. Re-running the same dataset is permitted and checked for idempotency. This is a single-dataset portfolio demo; distributed checkpointing and cross-dataset replacement are future work.

## Frontend

The assistant advertises only supported questions, displays the result table and evidence facts, links patients and source resources separately, and shows unsupported requests and service failures clearly. The graph and patient flows remain available. The data-quality page shows persisted run outcomes. The application prominently identifies synthetic data. README includes architecture, commands, a short demo script, evaluation results, and candid limitations.

## Verification

Unit and API tests cover strict plan validation, injection as parameter data, abstention, evidence coverage, model JSON failures, latest-result ordering, zero matches, and HTTP resource failures. Independent live evaluation computes expected patient IDs from NDJSON and compares them with API results for patient listing, condition cohorts, and latest HbA1c plus active Metformin. Browser tests cover supported answers, evidence inspection, and abstention. Live startup and ingestion must actually pass before the project is described as end-to-end verified. Docker recovery must preserve pre-existing volumes; deployment, Git history rewrites, and paid cloud services are outside this build.
