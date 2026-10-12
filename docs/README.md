# Documentation

Start with the [repository overview](../README.md). These documents describe the current implementation:

| Document | Use it to |
|---|---|
| [Run guide](GETTING_STARTED.md) | Install, start, verify, stop, recover and configure the demo |
| [Architecture](ARCHITECTURE.md) | Follow generation, storage, retrieval and provenance boundaries |
| [API contract](API_CONTRACT.md) | Inspect endpoints, plans, evidence and pagination semantics |
| [Graph schema](GRAPH_SCHEMA.md) | Understand resource identities, properties and reference edges |
| [Case study](CASE_STUDY.md) | Review decisions, measured evidence, tradeoffs and scope |

## Captured verification

[October 12 cleanup readiness](evidence/readiness-2026-10-12.json) records a fresh complete pipeline, 440 Python tests, five frontend unit tests, 21 controlled browser regressions and the live walkthrough.

The October 9 v1.0.0 snapshots are retained unchanged:

- [100-patient release evidence](evidence/portfolio-release.json)
- [Completed 1,000-patient benchmark](evidence/benchmark-1000.json)
- [Separately scoped initial fresh ingestion](evidence/initial-ingestion-1000.json)
- [Recorded application walkthrough](../portfolio/dist/assets/walkthrough.mp4)

For fresh evidence, run the checks in the run guide. Generated output belongs in ignored `artifacts/`, rather than replacing an earlier verified snapshot.

## Implementation entry points

Follow [pipelines/run_all.py](../pipelines/run_all.py) for the data lifecycle, [libs/rag/plans.py](../libs/rag/plans.py) and [queries.py](../libs/rag/queries.py) for question semantics, and [scripts/evaluate.py](../scripts/evaluate.py) for independent verification. Generator configuration lives in [libs/synthetic/config.py](../libs/synthetic/config.py); the unchanged official schema and its checksum/license are documented in [libs/fhir/schemas](../libs/fhir/schemas/README.md).

[Archive](archive/README.md) contains original specs, execution plans, prompts and earlier evidence. Its proposed features, dependencies and scale targets are historical, not current readiness claims.
