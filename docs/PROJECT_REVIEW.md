# Project review — 2026-10-05

> Historical October 5 review. The portfolio release addresses its remaining ingestion, validation, provenance, evaluation and delivery gaps; see [current case study](CASE_STUDY.md).

FHIRGraph now runs as an end-to-end local portfolio demo: seeded mock FHIR data → independent validation → persistent HAPI resources → Neo4j reference graph → constrained questions with exact source evidence. The earlier raw text-to-Cypher prototype has been replaced with strict plans and application-owned queries.

## Verified results

| Check | Result |
|---|---|
| Documented entry point | `make demo` completed: build/start, generate, validate, ingest, reconcile, smoke, evaluate |
| Live dataset | 100 patients, 1,468 encounters, 7,957 resources, seed 20260830 |
| Graph reconciliation | Exact match for 7,957 resource nodes and 17,130 explicit reference identities |
| HAPI reconciliation | Every generated resource-type count matches the live FHIR server |
| Data quality | All eight rules pass; zero duplicate IDs or dangling references |
| Independent answer evaluation | 17 live cases pass across all four intents, complete-page traversal, combined filters, boundary values, zero matches, and unsupported-filter abstention |
| Exact cited-source verification | 246 distinct FHIR resources resolve with matching identity, patient association, and cited fields |
| Python quality gate | Ruff, formatting, strict mypy, and 262 tests pass |
| Frontend quality gate | ESLint with zero warnings, TypeScript, layout unit regression, and production build pass |
| Browser verification | Nineteen controlled assistant/graph/cohort regressions plus one live patient/graph/audit/source/history walkthrough pass |
| Persistence | Exact FHIR resources remain after restarting the HAPI service |
| Idempotency and dataset isolation | Same-dataset reruns reconcile; a different dataset is refused before ingestion; the original dataset can rerun after that refusal |
| Local model | One experimental Ollama wording variation returns the same two independently expected patients after code-prefix normalization |

The live dataset SHA-256 is `8d5d941bf0a520b90eec6e915d007dbac38b48a70e8e1766dbe5507c366b91c8`. The default latest-HbA1c-above-8%/active-Metformin question returns `Patient/p-000044` (9.1%) and `Patient/p-000081` (8.2%), with exact Observation and MedicationRequest sources. The result size is bounded, not a population total.

The independent evaluator reads NDJSON without importing the query compiler or graph transformer. Its unit cases cover older-high/latest-normal results, missing and nonnumeric values, wrong units, non-active medication requests, timezone/nanosecond ties, duplicate medication matches, zero matches, history dates/order, and source field facts. It now follows complete results across bounded pages and checks each page's plan, displayed facts, metadata, and exact evidence. Premature termination, repeated pages, changed or invalid plans, displayed fact drift, source drift, wrong resource identity, failed source fetches, and reassignment to another patient fail evaluation. It checks the cited evidence subset, not all content in the FHIR server. Current pages and combined results are saved locally in `artifacts/demo/evaluation.json`; the portable [verification summary](evidence/portfolio-verification.json) and [browser capture](evidence/portfolio-demo.png) are portfolio evidence.

History includes standard AllergyIntolerance patient links and cites the exact recorded date and patient reference. The first example page returns 20 dated records; the live browser now loads all 80 directly linked records for the first patient across four pages. All assistant intents support continuation beyond 100 rows while each request remains capped at100. The UI preserves loaded rows after a failed or invalid continuation and does not silently merge repeated rows or a different plan.

A temporary, always-rolled-back Neo4j transaction verified the actual owned queries with 201 patient-list rows, 101 matching condition-cohort rows, 101 matching latest-lab/medication rows (also with the combined condition filter), and 103 history records. Original node counts remain7957 before and after; these are query correctness checks, not a larger persisted dataset or throughput benchmark. Earlier rolled-back allergy and read-only timezone probes remain documented in the evidence. Independent unit fixtures cover 101 patients and 102 history records, later-page source drift, and collisions in the missing-patient evaluation case. `make verify-demo` runs readiness, complete query/source checks, and the extended browser walkthrough in one command.

The host Python suite ran on Python 3.14.6. API containers use Python 3.12; builds and live container execution passed. GitHub Actions now includes Python 3.12 checks and the full Docker/browser integration job, but that remote workflow has not been executed here. The pinned HAPI image supports both linux/amd64 and linux/arm64.

## What changed

- Removed unused ORM/CRUD/seeding and conflicting Alembic scaffolding, the unused repair script and empty AI package, unused frontend dependencies/assets, scripted clinical stories, and speculative edge insights.
- Preserved standard `Encounter.class` serialization and original extra FHIR fields. Graph input validates supported types, canonical IDs, duplicates, and reference closure before touching Neo4j.
- Removed encounter co-occurrence `SUPPORTED_BY` edges. Explicit FHIR references remain directed graph edges; summary grouping edges are labeled as display groupings.
- Aligned API queries with the actual flattened graph schema. Added shared connections, bounded queries, correct age/condition filters, and working code/display autocomplete.
- Replaced arbitrary model Cypher with strict plans for patient lists, condition cohorts, patient history, and latest labs with active medication requests. Latest observations are selected before value/unit filtering, with deterministic ties and medication deduplication.
- Added exact canonical source IDs, FHIR field citations, a bounded resource proxy, and inspectable source JSON. The patient FHIR tab now retrieves the actual Patient resource.
- Persisted run stages, dataset hashes, eight rule outcomes, and stage-confirmed ingestion events. Added a single-dataset guard and PostgreSQL advisory lock. A pre-ingestion refusal is blocked, while an actual failed load remains protected as a possible partial write.
- Batched graph writes at 500 rows and used labeled/indexed edge endpoint matches. Added exact graph identity reconciliation alongside HAPI count reconciliation.
- Put HAPI resources in PostgreSQL's persistent `hapi` schema. Replaced the misleading JVM-only health probe with real API readiness checks, and enabled isolated Compose projects.
- Replaced fake successful dashboard/quality/mapping states with actual data or unavailable states. Added browser regressions and a live walkthrough.
- Added reproducible setup/demo/evaluation commands, documentation, a screenshot, and CI integration checks.
- Added bounded assistant result pages with complete traversal, stable ordering, exact per-page citations, Load more/retry/reset behavior, and independent completeness checks beyond the old 100-row ceiling. Review regressions also enforce the initial plan and all displayed source facts.

Docker Desktop initially failed with VM disk I/O errors. Recovery required restarting its processes, without resetting or deleting volumes. The final `fhirgraph-demo` stack is healthy; the original `infra_*` volumes and earlier verification volumes remain preserved. The earlier runtime blocker no longer prevents the live demonstration.

## Repository cleanup and handoff

The root repository previously tracked `apps/web` as a gitlink without `.gitmodules`, so a root checkout could omit the frontend. It is now a regular source directory in the working tree; the stale gitlink removal is staged. The nested Git metadata and a history bundle are preserved in ignored `.local-history/`. No commit or push was made. Review and commit the root changes before sharing a clone URL; the frontend files are currently untracked in the root until that commit.

Previously tracked generated artifacts, approximately 279 MB, remain preserved. New demo outputs are ignored. Removing historical generated data from tracking, while preserving local copies, would reduce repository size; rewriting existing Git history was outside this implementation.

## Remaining improvements

1. **More evaluated questions.** Add new intents with independent expected answers. Assistant patient lists, condition cohorts, latest-lab results, and histories now paginate completely; extend this to the separate cohort builder and patient detail projections. Optional model interpretation needs a larger paraphrase/unsupported-filter evaluation set before becoming the default. The evaluator no longer caps patient counts, but its in-memory oracle is not a large-scale benchmark.
2. **FHIR and terminology coverage.** Current models cover partial R4 resources and a small terminology catalog. External, contained, and URN references need explicit resolution; full profile validation and clinical realism require separate work. Positional flattened fields are convenient for the demo but fragile for broader sources.
3. **Reliable large ingestion.** The loader reads the full input into memory, and batches can leave partial writes. Add streaming, checkpoints, dataset namespaces, and a deliberate replacement/rollback strategy before scaling. Direct standalone loaders bypass the orchestration guard; manual store edits can cause drift.
4. **Broader retrieval and provenance.** The app provides constrained graph retrieval and deterministic evidence-backed answers. Vector retrieval, open-ended answer synthesis, claim coverage evaluation, and record-level provenance are future extensions. The lineage page remains an explicitly static mapping catalog.
5. **Public deployment.** Authentication, separate ingestion/read permissions, deployment operations, and real-data controls are needed for a hosted application. The delivered scope is a local synthetic-data portfolio demo.

A separate offline 1,000-patient generation/validation run produced 15,118 encounters, 80,621 resources, and 174,998 explicit references, with all eight rules passing. Its hash is `caf7b16900d4863f104920844a73a67caf3215af408fd8d2e31c40a5d04f5846`. This demonstrates artifact generation and validation, not live database performance at that scale.
