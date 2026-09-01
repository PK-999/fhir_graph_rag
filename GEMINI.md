# FHIRGraph — Gemini Project Instructions

## Mission
Build a portfolio-quality healthcare knowledge-graph product using synthetic FHIR R4 data.

The product must:
1. Generate exactly 1,000 synthetic patients.
2. Generate 10–20 encounters per patient.
3. Preserve FHIR referential integrity.
4. Load normalized clinical relationships into Neo4j.
5. Provide Patient 360, Timeline, Graph Explorer, Cohort Builder, Data Quality, Lineage, and AI Query experiences.
6. Use synthetic data only. Never imply that generated data is clinically valid for patient care.

## Source of truth
Before changing architecture or data contracts, read only the relevant file:
- `docs/PRODUCT_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/DATA_GENERATION_SPEC.md`
- `docs/GRAPH_SCHEMA.md`
- `docs/API_CONTRACT.md`
- `docs/ENGINEERING_STANDARDS.md`
- `docs/BUILD_PLAN.md`
- `docs/AGENT_WORKFLOW.md`

Do not repeatedly load every document. Use progressive context.

## Operating rules
- Plan before implementing a milestone.
- Make small, reviewable changes.
- Do not rewrite working modules unnecessarily.
- Prefer deterministic code over LLM-generated runtime data.
- Never hard-code mock patient records in application code.
- All generated data must be reproducible from a seed.
- Every FHIR reference must resolve or be explicitly documented as external.
- All code paths touching FHIR data require automated tests.
- Use `MERGE`/idempotent upserts for Neo4j ingestion.
- Never allow an LLM unrestricted write access to Neo4j.
- Do not add dependencies unless they provide clear value.
- Keep modules small and typed.
- Fail loudly on referential-integrity violations.

## Default stack
Frontend: Next.js + TypeScript + Tailwind + shadcn/ui + Cytoscape.js
API: Python + FastAPI + Pydantic
FHIR: HL7 FHIR R4
FHIR server: HAPI FHIR
Graph: Neo4j
Metadata/audit: PostgreSQL
Synthetic data: deterministic Python generator, optionally seeded/reference-checked against Synthea patterns
Observability: OpenTelemetry + Prometheus/Grafana
Local environment: Docker Compose
Tests: pytest + Vitest/Playwright as appropriate

## Definition of done for every task
A task is not complete until:
- implementation is present;
- tests are present or explicitly unnecessary;
- tests/lint/type-check pass;
- affected docs/contracts are updated;
- no dangling FHIR references are introduced;
- no secrets or real PHI are committed.

## Communication
When starting a task:
1. State the files you intend to inspect.
2. State the files you intend to modify.
3. Implement.
4. Run the narrowest useful verification.
5. Report only changes, validation results, and unresolved issues.

Avoid long explanations unless requested.
