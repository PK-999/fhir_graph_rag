# FHIRGraph Portfolio Demo Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for implementation, with independent frontend, pipeline, and evaluation tasks delegated through superpowers:dispatching-parallel-agents. Preserve the existing uncommitted work; do not stage or commit.

**Goal:** A reproducible local FHIR-to-graph portfolio demo with grounded answers and independent end-to-end evaluation.

**Architecture:** FastAPI compiles strict clinical query plans to parameterized Neo4j templates and presents deterministic evidence-backed answers. HAPI holds exact FHIR resources, PostgreSQL records pipeline results, and the Next.js UI exposes answers and evidence.

**Tech Stack:** Existing Python/Pydantic/FastAPI, Neo4j, HAPI FHIR, asyncpg/PostgreSQL, Next.js, local Ollama, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-04-portfolio-demo-design.md`

## Global constraints

- Synthetic healthcare data only; local Docker is the portfolio target.
- Preserve existing data, volumes, credentials, and uncommitted changes. No paid services or deployment.
- Application-owned parameterized queries only. Results are limited, not population totals.
- Latest observations are selected before threshold/unit filtering; ties use descending canonical resource ID.
- Unsupported questions abstain. Every clinical fact has an exact FHIR resource and field path.

## Review focus

- A latest normal or missing-value lab must exclude a patient whose older result was elevated.
- Multiple qualifying medications must not duplicate patients; timestamp ties must be deterministic.
- Unsupported recommendations and extra model fields must never cause arbitrary graph execution.
- Failed ingestion must produce a failed run, with no misleading successful audit events.
- A different dataset must not silently merge with existing registered data.

## Tasks

### 1. Grounded question engine (primary agent)

Files: `libs/rag/{plans,queries,evidence}.py`, assistant router and tests; resource proxy router/main and tests.

Interfaces: `QueryPlan` fields `intent`, `limit` (1–100, default 20), `condition_code`, `lab_code`, `medication_code`, `threshold`, `comparison` (`gt`, `gte`, `lt`, `lte`), `unit`, `patient_id`. Intents: patient_list, condition_cohort, latest_lab_medication, patient_history. API response fields are specified in the design.

- [x] Write tests for strict schema, supported parsing, parameterization, latest-before-filter query structure, and evidence field paths; observe failures.
- [x] Implement typed plans, deterministic demo parsing, constrained local-model fallback, parameterized templates, and evidence answers. Remove the old arbitrary Cypher execution path.
- [x] Add exact-resource proxy with supported type/ID validation and bounded upstream errors.
- [x] Run focused tests, Ruff and mypy; resolve regressions.

### 2. Persisted pipeline truth (pipeline agent)

Files: pipeline orchestration/config/metadata, relevant API metadata routes, PostgreSQL SQL, pipeline tests.

Interfaces: Existing pipeline steps and DQ report remain consumable. `pipeline_runs.config_snapshot` records `dataset_hash`, patient count/seed/output, and stage outcomes without credentials; ingestion_events retain existing fields. Existing `/data-quality/summary` response remains compatible.

- [x] Write failing tests for success/failure auditing, eight quality results, and dataset mismatch before ingestion.
- [x] Persist run, quality, and stage-confirmed ingestion events; fail closed on registered dataset mismatch.
- [x] Run pipeline/metadata tests and targeted static checks; report exact contract and limitations.

### 3. Evidence-first assistant UI (frontend agent)

Files: assistant page/components, browser tests, UI copy.

Interfaces: POST /assistant/query response from the spec. Evidence `source_url` is an API-relative path, prefixed with NEXT_PUBLIC_API_URL; `patient_id` links to patient detail. Questions supported by deterministic parsing include “List five patients”, “Find patients with type 2 diabetes”, “Find patients whose latest HbA1c is above 8% with active Metformin”, and “Show history for Patient/<id>”.

- [x] Read apps/web/AGENTS.md and installed Next.js guide.
- [x] Add browser tests for results, observation/medication facts and source inspection, zero matches, and abstention; observe failures.
- [x] Implement examples, tables, evidence inspection, honest scope copy, and error handling.
- [x] Run lint, types, unit/build, and relevant browser checks.

### 4. Independent live evaluation (evaluation agent)

Files: `scripts/evaluate.py`, evaluation unit tests, machine-readable report output.

Interfaces: `--input <dataset directory> --api-url <.../api/v1> --output <report.json>`. Read NDJSON directly, calculate expected patient IDs for diabetes and latest HbA1c >8% with active Metformin, and POST the advertised natural-language questions with explicit limit 100 through a plan where necessary. Compare exact result ID sets and evidence resource IDs/field values; unsupported treatment advice must abstain. Handle truncation by evaluating a <=100-patient demo dataset or refusing larger inputs explicitly.

- [x] Write independent oracle tests: older high/latest normal, missing value, wrong unit, medication status, ties, duplicate medications, zero matches.
- [x] Implement JSON report with expected/actual sets, pass/fail per case, and nonzero exit on failures.
- [x] Run unit tests and report how to invoke live evaluation.

### 5. End-to-end demo and portfolio handoff (primary agent)

- [x] Recover Docker without resetting existing volumes; start a fresh isolated stack and fix evidenced integration bugs.
- [x] Run full pipeline on 20–100 synthetic patients, reconcile both stores, and verify same-dataset rerun idempotency.
- [x] Run independent API evaluation and real-browser user flows.
- [x] Run make check and request independent final code review; fix material findings.
- [x] Update README, architecture/API docs and project review with actual results, demo commands, and limitations. Record any external runtime blocker candidly.

## Completion evidence and adjustments

Completed on 2026-10-04. `make demo` passed on a fresh isolated 100-patient stack; `make check` passed with 221 Python tests and the production web build. Seven independent live answer cases, eleven controlled Chromium cases, and the real browser walkthrough passed. Exact graph identities and HAPI counts reconciled, FHIR survived a HAPI restart, and same-dataset reruns remained idempotent. A mismatch refusal followed by an original-dataset rerun passed without store changes.

Live checks exposed unindexed edge endpoint matches and nonpersistent HAPI storage. Graph loading now uses labeled indexed lookups in batches of 500; HAPI uses PostgreSQL's separate `hapi` schema. Final independent review found and prompted fixes for dataset-guard poisoning and false provenance copy on summary edges. The patient FHIR tab now fetches the actual resource.

The frontend gitlink had to be removed from the root index to make frontend source shareable; no source changes were otherwise staged or committed. Its nested Git metadata and history bundle are preserved in ignored `.local-history/`. Existing generated data and Docker volumes were preserved.

See `docs/PROJECT_REVIEW.md` and `docs/evidence/portfolio-verification.json` for measured evidence and remaining work. Remote CI and public deployment were not run.
