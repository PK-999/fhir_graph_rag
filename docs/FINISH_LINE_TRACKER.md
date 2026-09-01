# FHIRGraph Finish-Line Tracker

**Source design:** `docs/superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md`  
**Status legend:** `[ ]` not started, `[~]` in progress, `[x]` verified, `[!]` blocked

## Discovery and decisions

- [x] Select polished synthetic-data research/portfolio scope.
- [x] Select 100,000-patient reference scale.
- [x] Select clinical informatics researcher as primary persona.
- [x] Select practicing clinician as secondary persona.
- [x] Approve Research/Clinical view switcher.
- [x] Approve workstation-first deployment with cloud-ready adapters.
- [x] Approve modular-platform architecture.
- [x] Approve typed plan and deterministic query compilation.
- [x] Approve registry checksum enforcement.
- [x] Approve immutable fact ledger and numeric-integrity enforcement.
- [x] Approve UI/UX direction.
- [x] Approve testing, performance, and observability gates.

## Verified baseline

- [x] Python tests: 43 passed.
- [!] Frontend lint: four errors and nine warnings.
- [!] Ruff: 35 issues.
- [!] Strict mypy: 100 errors in 39 files.
- [x] Webpack production build completes.
- [!] Default Turbopack build fails in the current execution environment.
- [!] Neo4j and PostgreSQL were unavailable during the live check.
- [!] Health endpoint reported database readiness incorrectly.
- [!] Common data APIs returned HTTP 500 while health returned HTTP 200.
- [!] Two unrelated projects occupied port 3000; the FHIRGraph web app was not the app being served there.
- [!] Direct Chrome control attachment was rejected; accepted UX screenshots are pending.

## Stage 1 — Reliable development baseline

- [ ] Define collision-free, configurable ports and a startup preflight.
- [ ] Separate liveness from real dependency readiness.
- [ ] Add deterministic local service startup and seed instructions.
- [ ] Replace permissive API tests with exact contract/integration tests.
- [ ] Resolve frontend lint errors and warnings.
- [ ] Resolve Ruff findings.
- [ ] Resolve strict mypy findings.
- [ ] Make the supported production build path explicit and reproducible.
- [ ] Establish a green CI-quality baseline.

## Stage 2 — Registry and graph v2

- [ ] Create the typed schema registry.
- [ ] Export canonical registry JSON and checksum.
- [ ] Add dataset and graph manifest compatibility checks.
- [ ] Implement stable resource projections and terminology nodes.
- [ ] Implement registry-defined relationships and indexes.
- [ ] Add transactional streaming load with checkpoints.
- [ ] Add offline bulk-import adapter.
- [ ] Reconcile nodes, relationships, references, and dataset metadata.
- [ ] Add registry drift and graph integration tests.

## Stage 3 — Typed API facade

- [ ] Define versioned response and problem-details models.
- [ ] Generate frontend types from OpenAPI.
- [ ] Implement cursor pagination and allowlisted sorting/filtering.
- [ ] Rebuild dashboard, patient, timeline, graph, cohort, DQ, and lineage queries against graph v2.
- [ ] Add explicit unavailable, partial, stale, empty, and zero-result semantics.
- [ ] Add job progress and cancellation contracts.
- [ ] Add API contract and integration coverage.

## Stage 4 — Trustworthy question engine

- [ ] Define typed intents and `QueryPlan` models.
- [ ] Implement terminology resolution.
- [ ] Add the provider-neutral Ollama adapter.
- [ ] Implement deterministic parameterized compilation.
- [ ] Enforce registry tokens, read-only role, `EXPLAIN`, depth, row, cost, and timeout limits.
- [ ] Implement immutable fact ledger and evidence model.
- [ ] Implement numeric-safe placeholder rendering and deterministic fallback.
- [ ] Create at least 100 golden questions.
- [ ] Reach at least 95% plan and answer accuracy.
- [ ] Demonstrate 100% mutation rejection and evidence coverage.

## Stage 5 — Research experience

- [ ] Rebuild the shared application shell and truthful service status.
- [ ] Add the Research/Clinical view switcher and persistence.
- [ ] Build the research dataset overview.
- [ ] Build the composable cohort builder and saved definitions.
- [ ] Build the evidence-first assistant workspace.
- [ ] Build bounded graph exploration with table alternative.
- [ ] Add complete loading, empty, error, stale, partial, and recovery states.

## Stage 6 — Clinical experience

- [ ] Build the patient-centered workspace.
- [ ] Add active problems, medications, allergies, and abnormal results.
- [ ] Build the longitudinal timeline and evidence navigation.
- [ ] Preserve patient context across views.
- [ ] Keep technical query details available but collapsed.
- [ ] Verify clinical state semantics do not depend on color alone.

## Stage 7 — 100,000-patient scale

- [ ] Generate and validate the versioned dataset.
- [ ] Load HAPI and graph projections and reconcile counts.
- [ ] Record generation, load, storage, memory, and resume metrics.
- [ ] Benchmark representative cold and warm queries.
- [ ] Meet API, cache, UI, and interaction budgets.
- [ ] Optimize only measured bottlenecks and record before/after evidence.

## Stage 8 — Release verification

- [ ] Run all automated quality gates.
- [ ] Complete direct-Chrome desktop and narrow-width journeys.
- [ ] Complete keyboard, focus, zoom/reflow, and reduced-motion checks.
- [ ] Inspect console, network, rendering stability, and performance traces.
- [ ] Save and inspect accepted audit screenshots.
- [ ] Publish UX/accessibility audit and evidence limits.
- [ ] Publish accuracy and performance reports.
- [ ] Synchronize all architecture, API, schema, README, and tracker documents.

