# FHIRGraph Finish-Line Design

**Status:** Approved design  
**Date:** 2026-09-01  
**Primary persona:** Clinical informatics researcher  
**Secondary persona:** Practicing clinician  
**Reference scale:** 100,000 synthetic patients  
**Reference deployment:** One capable workstation using Ollama, with replaceable storage and inference adapters

## 1. Outcome

FHIRGraph will become a polished synthetic-data research and portfolio platform that:

- generates and validates reproducible FHIR R4 datasets;
- projects query-critical clinical facts into a versioned Neo4j knowledge graph;
- supports research cohorts, patient exploration, lineage, data quality, and graph workflows;
- answers natural-language questions through typed plans and deterministic execution;
- provides resource-level evidence for every factual answer;
- demonstrates credible performance at 100,000 synthetic patients;
- offers Research and Clinical presentation modes over the same facts; and
- runs locally with PostgreSQL, Neo4j, HAPI FHIR, FastAPI, Next.js, and Ollama.

This remains a synthetic-data demonstration. Authentication, consent, real-PHI governance, clinical decision support certification, and regulated production operation are outside the finish-line scope.

## 2. Verified Baseline

The design is based on repository inspection and local checks performed on 2026-09-01.

### Working foundations

- The generator, FHIR models, graph loader, FastAPI application, and Next.js application are present.
- The Python test suite currently reports 43 passing tests.
- Ollama is available locally with `llama3.1:latest`.
- A webpack production build completes and TypeScript compilation succeeds.
- The frontend already contains Dashboard, Patient Registry, Patient 360, Timeline, Graph Explorer, Cohorts, Data Quality, Lineage, and Assistant routes.

### Current failures and risks

- The API health endpoint can report Neo4j and PostgreSQL as connected when neither service is reachable.
- Data-bearing API endpoints returned HTTP 500 while health returned HTTP 200.
- Unrelated projects were occupying common frontend ports, making the apparent application at `localhost:3000` nondeterministic.
- The current graph transformer emits flattened snake-case properties and relationships such as `SUBJECT`, while API queries and the assistant prompt use different property and relationship names.
- The Cohort UI sends `conditions`; the API expects `condition_codes`.
- The assistant asks Ollama to generate executable Cypher directly and validates it with keyword matching.
- The assistant's narrative generation can change or invent numeric facts.
- API tests accept broad alternatives such as success or service unavailable, so contract breakage can pass.
- Frontend lint has four errors and nine warnings.
- Ruff reports 35 issues.
- Strict mypy reports 100 errors across 39 files.
- The default Turbopack build fails in the current execution environment while the webpack build passes; this is tracked as an environment/tooling issue until reproduced outside that constrained build context.
- The current automated browser test checks presence of headings more than user-visible outcomes.
- Chrome capture has not yet been accepted as audit evidence because this chat's Chrome control attachment continued to reject the automation session. Direct Chrome verification remains a release gate.

## 3. Architectural Decision

Use an evolutionary modular platform rather than either a microservice rewrite or a presentation-only repair.

### Why

- It preserves useful existing code and the familiar stack.
- It creates strong contracts without adding distributed-system overhead to a workstation deployment.
- It supports 100,000-patient benchmarks through streaming ingestion, indexes, projections, and bounded queries.
- It makes future hosted storage or inference possible through adapters instead of premature service decomposition.

### Logical flow

```text
Synthetic generator
  -> validation and reconciliation
  -> versioned NDJSON/Parquet artifacts
      -> optional HAPI FHIR interoperability copy
      -> streaming graph projection
          -> Neo4j clinical graph
          -> PostgreSQL run, lineage, evaluation, and benchmark metadata

Next.js UI
  -> typed FastAPI facade
      -> patient/cohort/graph query services
      -> constrained question engine
          -> Ollama intent/entity adapter
          -> deterministic plan compiler
          -> bounded Neo4j execution
          -> immutable fact ledger and evidence renderer
```

HAPI FHIR is not placed on the latency-sensitive UI path. Versioned generated artifacts are the reproducible source of truth; Neo4j is a derived clinical projection.

## 4. Module Boundaries

The codebase will retain a modular monolith with the following responsibilities:

- `libs/fhir`: typed FHIR R4 subset, serialization, reference extraction, and validation.
- `libs/synthetic`: deterministic dataset and scenario generation.
- `libs/clinical_graph`: authoritative schema registry, projection, terminology links, and load strategies.
- `libs/query_engine`: typed query plans, terminology resolution, deterministic compilation, policy validation, execution, fact ledger, and evidence.
- `libs/evaluations`: golden questions, graders, benchmark runners, and regression reports.
- `apps/api`: typed transport, orchestration, readiness, limits, and error mapping.
- `apps/web`: shared design system, Research mode, Clinical mode, and resilient API states.
- `pipelines`: resumable dataset generation, validation, graph/HAPI loading, reconciliation, and scale benchmarks.

Modules communicate through typed interfaces and versioned artifacts. Domain logic must not depend on FastAPI, React, or a specific inference provider.

## 5. Registry Enforcement

The registry is the highest-priority integrity mechanism.

### Authoritative source

A typed Python registry defines:

- supported node labels;
- stable projected properties and their types;
- relationship types and allowed source/target pairs;
- terminology systems and normalized code fields;
- indexes and uniqueness constraints;
- supported query operations and aggregations; and
- the public schema version.

The registry exports a canonical JSON representation with a deterministic checksum.

### Enforcement points

- Every generated dataset manifest contains the schema version and checksum.
- Every graph load writes the same version and checksum to graph metadata.
- API readiness compares its compiled registry checksum with the active graph.
- A mismatch makes query readiness fail with a clear migration message.
- Ingestion can only create registry-defined labels, relationships, and projected properties.
- The compiler accepts enums, not arbitrary label/property strings.
- Cypher literals are selected only through fixed registry mappings; user or model text is always parameterized data.
- Documentation tables are generated from the registry artifact.
- CI regenerates the artifact and fails on uncommitted drift.
- Contract fixtures prove ingestion, API models, compiler mappings, and indexes use the same registry.

This removes the present class of failures where transformer output, handwritten API Cypher, and assistant prompts silently disagree.

## 6. Clinical Graph Model

### Resource nodes

The first supported graph version includes:

- `Patient`
- `Encounter`
- `Condition`
- `Observation`
- `MedicationRequest`
- `Procedure`
- `DiagnosticReport`
- `AllergyIntolerance`
- `Practitioner`
- `Organization`

### Terminology nodes

Normalized concept nodes represent the curated SNOMED CT, LOINC, RxNorm, and ICD-10 catalogs used by the synthetic generator.

### Stable relationships

FHIR references project into registry-defined relationships including:

- `SUBJECT`
- `ENCOUNTER`
- `PERFORMER`
- `SERVICE_PROVIDER`
- `BASED_ON`
- `RESULT`
- `CODED_AS`

### Common properties

Query-critical properties include dataset version, canonical resource key, FHIR ID, status, display, clinical/effective date, normalized code, numeric value, unit, provenance hash, and last-updated time. Patient nodes additionally expose explicitly defined search/sort projections.

Raw resources remain in versioned artifacts. Neo4j does not become an ungoverned duplicate document store.

### Loading

- Use stable resource keys and idempotent writes.
- Load nodes before relationships.
- Stream bounded batches and checkpoint each partition.
- Keep a transactional loader for development and incremental runs.
- Provide an offline bulk-import adapter for full 100,000-patient rebuild benchmarks.
- Reconcile counts and unresolved references after every load.
- Record dataset, registry, duration, throughput, failure, and retry metadata.

## 7. Trustworthy Natural-Language Questions

### Execution pipeline

1. Classify the question into an allowlisted intent.
2. Resolve clinical terms through the terminology catalog.
3. Ask Ollama for a typed `QueryPlan`, not Cypher.
4. Validate the plan using Pydantic and domain rules.
5. Compile the plan deterministically into parameterized Cypher.
6. Run `EXPLAIN` and enforce read-only operations, allowed schema tokens, depth, cost, row, and timeout limits.
7. Execute using a read-only Neo4j account.
8. Construct an immutable fact ledger and evidence set.
9. Render the factual answer from server-owned facts.

Common patient, condition, medication, observation, temporal, and cohort questions use deterministic plan templates. Ambiguous or unsupported questions request clarification instead of guessing.

### Numeric-integrity guarantee

No numeric literal displayed as a fact may originate from Ollama.

- Query results are normalized into immutable typed facts with stable fact IDs.
- The deterministic renderer owns all values, units, dates, counts, comparisons, and formatting.
- Optional cosmetic phrasing receives opaque placeholders such as `{{fact_1}}`, not raw values.
- The cosmetic response must match the exact allowed placeholder set and must not contain numeric literals.
- The server parses and validates the cosmetic response before replacing placeholders from the ledger.
- Evidence references the same fact IDs used by the renderer.
- Any validation failure uses a deterministic template.
- Quantitative answers can bypass cosmetic phrasing entirely.

### Evaluation bar

A versioned suite of at least 100 representative questions must demonstrate:

- at least 95% correct query plans;
- at least 95% correct final answers;
- 100% mutation rejection;
- 100% evidence coverage for factual results; and
- explicit tracking of ambiguity, terminology, latency, and regression failures.

## 8. Product and UX Design

### Shared shell

- Persistent Research/Clinical view switcher.
- Global patient and cohort search.
- Dataset-version and synthetic-data indicators.
- Real service readiness and background-job state.
- Clear active navigation, collapsible sidebar, theme control, and keyboard command menu.
- Explicit unavailable, stale, partial, empty, and zero-result states.

The current excessive translucent surfaces, decorative motion, and hover translation will be reduced. Visual styling will favor calm neutral surfaces, strong hierarchy, meaningful density, and restrained clinical/research color semantics.

### Research mode

- Dataset overview: provenance, quality gates, resource distributions, ingestion history, saved cohorts, recent questions, and benchmark status.
- Cohort builder: nested AND/OR groups, terminology autocomplete, exclusions, temporal rules, live estimates, save/compare/export, and reproducibility metadata.
- Assistant: answer first; then interpretation, assumptions, terminology matches, evidence, confidence, timing, and collapsible plan/Cypher details.
- Graph explorer: bounded neighborhood, progressive expansion, filters, legend, search, layout controls, synchronized inspector, and table alternative.
- Every analytical result exposes derivation and dataset version.

### Clinical mode

- Patient-centered workspace with identity, demographics, active problems, medications, allergies, recent abnormal results, and timeline.
- Patient context persists while switching summary, timeline, results, medications, and graph views.
- Evidence links navigate to the relevant event and FHIR resource.
- Technical query details are available but collapsed by default.
- Abnormal or urgent states use text, iconography, and structure in addition to color.

### Accessibility and responsiveness

- WCAG 2.2 AA target.
- Complete keyboard paths and visible focus.
- Semantic tables and textual chart/graph alternatives.
- Reduced-motion support.
- At least 44px primary interactive targets.
- Responsive reflow and 200% zoom resilience.
- URL-persisted filters and cursor pagination.
- Virtualization only for demonstrated large-list bottlenecks.

## 9. API and Failure Contracts

- Generate frontend types from the versioned OpenAPI document.
- Use a consistent response envelope for data, pagination, dataset version, provenance, warnings, and request ID.
- Use stable problem-details error codes for dependency unavailable, schema mismatch, validation failure, timeout, ambiguity, unsupported question, and partial data.
- Health endpoints distinguish process liveness from dependency readiness and perform bounded real checks.
- Failed fetches never become empty arrays or zero metrics without a visible degraded-state marker.
- All list endpoints use bounded cursor pagination and allowlisted sorting/filtering.
- Long jobs expose status, progress, cancellation, timestamps, and resumable checkpoints.

## 10. Performance and Scale

The reference benchmark uses 100,000 patients and records hardware, software versions, dataset checksum, cold/warm state, and query parameters.

Measure:

- generation throughput and artifact size;
- graph import throughput and reconciliation;
- database size and peak memory;
- restart/resume behavior;
- indexed patient search;
- Patient 360 and timeline;
- one-hop graph expansion;
- representative cohorts;
- dashboard summaries; and
- assistant end-to-end stages.

Targets:

- non-AI API p95 below 500 ms;
- cached summaries below 150 ms;
- initial useful UI content below 2 seconds on the reference workstation;
- interaction feedback below 100 ms; and
- progress plus cancellation for operations longer than 2 seconds.

Dashboard aggregates and expensive repeated cohorts use bounded caches invalidated by dataset version. Optimization follows measured query plans and traces, not assumed bottlenecks.

## 11. Testing and Verification

### Automated layers

- Unit tests for registry, transformer, compiler, validators, fact ledger, and UI state reducers.
- Golden FHIR fixtures for references, terminology, dates, quantities, and provenance.
- Neo4j/PostgreSQL integration tests with real service containers.
- API contract tests with exact statuses and response schemas.
- Component tests for forms, validation, modes, errors, keyboard behavior, and accessible names.
- End-to-end workflows for dashboard, registry, Patient 360, timeline, cohorts, graph, assistant evidence, and degraded services.
- Query evaluation and performance regression suites.

### Direct Chrome release gate

The real application must be verified in the user's connected Chrome profile at desktop and narrow viewports. The audit covers:

- visible layout and content hierarchy;
- navigation and focus order;
- keyboard-only operation;
- loading, empty, error, partial, and recovery states;
- network and console failures;
- zoom/reflow and reduced motion;
- assistant evidence navigation;
- performance traces; and
- accepted screenshots with step-specific UX/accessibility notes.

This gate is pending until the Chrome automation attachment is operational in the executing chat. Playwright is not a substitute for the requested direct-Chrome audit, though it remains part of CI.

## 12. Observability

- Correlate request, job, dataset, and question IDs across UI diagnostics, logs, metrics, and traces.
- Record query latency, rows scanned/returned, cache hits, plan rejection reasons, Ollama stage latency, ingestion throughput, failed resources, and evaluation accuracy.
- Export Prometheus metrics and OpenTelemetry spans.
- Store evaluation and benchmark summaries in PostgreSQL and versioned report artifacts.
- Retry only transient ingestion failures with bounded backoff; interactive questions fail clearly and do not retry unpredictably.

## 13. Delivery Sequence

1. Stabilize local startup, port selection, readiness, lint, typing, build, and integration fixtures.
2. Add the schema registry and graph-v2 projection.
3. Rebuild typed APIs and generated frontend contracts.
4. Add the constrained query engine, fact ledger, and evaluation harness.
5. Rework the shell and Research workflows.
6. Build the Clinical patient workspace and view switcher.
7. Generate, import, and benchmark 100,000 patients; optimize measured bottlenecks.
8. Complete direct-Chrome UX, accessibility, resilience, and performance verification.
9. Synchronize documentation and publish the final evidence report.

Each stage must leave a demonstrably working product slice and pass its narrow automated gates before the next stage begins.

## 14. Decision Record

| Decision | Reason | Rejected alternative |
|---|---|---|
| Modular monolith | Strong boundaries without workstation-hostile operations | Premature microservices |
| 100,000-patient reference dataset | Credible portfolio scale with practical local execution | Staying at 1,000 or requiring 1 million |
| Versioned clinical projection | Predictable queries and shared contracts | Arbitrary flattened FHIR properties |
| Registry checksum enforcement | Prevents silent ingestion/query/prompt drift | Documentation-only schema agreement |
| Typed plans and deterministic compiler | Testable accuracy and safe execution | Direct LLM-to-Cypher |
| Immutable fact ledger | Gives an enforceable numeric-integrity guarantee | Unconstrained LLM summarization |
| Research/Clinical modes | Serves both personas without duplicating truth | Separate applications |
| HAPI off the UI hot path | Keeps interoperability without avoidable latency | Routing all reads through HAPI |
| Ollama adapter | Meets local-first requirement and avoids provider lock-in | OpenAI-specific runtime |
| Evidence-first answers | Makes analytical claims inspectable | Opaque conversational answers |

## 15. Completion Criteria

The finish line is reached only when:

- all required services start predictably and readiness is truthful;
- lint, type checks, builds, unit, integration, component, and end-to-end tests pass;
- graph and API contracts share an enforced registry checksum;
- the 100-question evaluation meets its accuracy and safety thresholds;
- every factual assistant answer contains valid evidence;
- numeric-integrity adversarial tests pass;
- the 100,000-patient dataset is generated, loaded, reconciled, and benchmarked;
- performance budgets are met or documented with evidence and an accepted exception;
- Research and Clinical workflows pass the direct-Chrome audit;
- accessibility risks identified by the audit are resolved or explicitly documented; and
- architecture, graph schema, API contract, build plan, implementation tracker, README, evaluation report, benchmark report, and UX audit agree with the shipped system.

