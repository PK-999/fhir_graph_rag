# Build Plan

> **Historical roadmap:** The milestone record below and the September [finish-line tracker](FINISH_LINE_TRACKER.md) retain earlier plans, including a proposed 100,000-patient target. They do not describe the current release or establish that scale as verified. For the verified 100-patient portfolio demo, current checks, and remaining work, see the [README](../README.md) and [project review](PROJECT_REVIEW.md), updated 2026-10-05.

## Milestone 0 — repository bootstrap

**Status (verified 2026-09-02): complete.** Evidence: [`evidence/milestone-0-verification.md`](evidence/milestone-0-verification.md).

Deliver:
- monorepo structure
- Docker Compose
- environment examples
- lint/test commands
- CI skeleton

Exit criteria:
- one command starts dependencies;
- API and web health pages work.

## Milestone 1 — deterministic synthetic FHIR
Deliver:
- configuration model
- resource ID factory
- patient generator
- practitioner/organization pools
- encounter generator
- 3 initial clinical scenarios
- FHIR serialization
- referential-integrity validator
- data-quality report

Develop with 20 patients first.

Exit criteria:
- exact configured count;
- 10–20 encounters each;
- zero dangling references;
- deterministic hash test passes.

## Milestone 2 — full 1,000-patient dataset
Add all V1 scenario templates and resource types.

Exit criteria:
- 1,000 patients generated;
- approximately 15,000 encounters;
- all DQ gates pass;
- aggregate summary produced.

## Milestone 3 — HAPI FHIR
Deliver:
- transaction/bulk loader
- reconciliation counts
- retry and error handling

Exit criteria:
- generated resource counts reconcile with server counts.

## Milestone 4 — knowledge graph
Deliver:
- canonical graph transformer
- Neo4j constraints
- idempotent loader
- graph reconciliation tests

Exit criteria:
- graph contains all required resource relationships;
- repeated load does not duplicate nodes/edges.

## Milestone 5 — APIs
Deliver patient, timeline, graph, cohort, DQ, provenance APIs.

## Milestone 6 — frontend
Deliver:
- Dashboard
- Patient Search
- Patient 360
- Timeline
- Graph Explorer
- Cohort Builder
- Data Quality
- Lineage

## Milestone 7 — AI
Start with template-based NL query planning.
Only after correctness is established, allow constrained generated Cypher.

Exit criteria:
- every answer returns evidence;
- mutation attempts rejected.

## Milestone 8 — observability and polish
- metrics
- traces
- error states
- loading states
- responsive UI
- README/demo script

## Milestone 9 — finish-line modernization

Deliver:

- truthful local startup and dependency readiness;
- versioned schema registry and clinical graph projection;
- typed APIs and generated frontend contracts;
- constrained Ollama-backed question planning with deterministic compilation;
- immutable fact ledger, numeric-integrity enforcement, and evidence-first answers;
- Research and Clinical presentation modes;
- 100,000-patient generation, ingestion, reconciliation, and benchmarks;
- direct-Chrome UX, accessibility, resilience, and performance verification; and
- synchronized documentation and evidence reports.

Exit criteria are defined in `docs/FINISH_LINE_TRACKER.md` and the approved finish-line design.
