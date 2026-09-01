# Architecture

> **Target architecture notice (2026-09-01):** This document describes the original/current structure. The approved finish-line target—including the registry-enforced graph, constrained Ollama question engine, Research/Clinical UX, and 100,000-patient scale—is specified in [`superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md`](superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md). Implementation must not mark this target as shipped until the tracker gates pass.

## Logical flow

```text
Synthetic Generator
  -> FHIR R4 Bundles / NDJSON
  -> Validation
  -> HAPI FHIR
  -> Ingestion Service
  -> Canonical Graph Representation
  -> Neo4j

Raw FHIR JSON -----------------------> Object/local storage
Run metadata + DQ -------------------> PostgreSQL

Neo4j + PostgreSQL
  -> FastAPI
  -> Next.js application
  -> Graph Explorer / Patient 360 / Cohorts / AI Assistant
```

## Repository layout

```text
fhir_graph_rag/
├── apps/
│   ├── api/                       # FastAPI application
│   │   ├── app/
│   │   │   ├── main.py            # app factory, lifespan, middleware
│   │   │   ├── config.py          # pydantic-settings, env parsing
│   │   │   ├── dependencies.py    # DI: Neo4j driver, PG pool, FHIR client
│   │   │   ├── routers/
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── patients.py
│   │   │   │   ├── graph.py
│   │   │   │   ├── cohorts.py
│   │   │   │   ├── data_quality.py
│   │   │   │   ├── lineage.py
│   │   │   │   └── assistant.py
│   │   │   ├── schemas/           # Pydantic response/request models
│   │   │   ├── services/          # thin orchestration layer (calls into libs)
│   │   │   └── middleware/        # CORS, request-id, timing, safety banner
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   │
│   └── web/                       # Next.js frontend
│       ├── src/
│       │   ├── app/               # App Router pages
│       │   ├── components/        # shared UI components
│       │   ├── lib/               # API client, helpers, types
│       │   └── styles/
│       ├── public/
│       ├── next.config.ts
│       ├── tailwind.config.ts
│       ├── tsconfig.json
│       ├── Dockerfile
│       └── package.json
│
├── libs/                          # shared Python libraries (no framework deps)
│   ├── fhir/                      # FHIR models, serialization, reference validation
│   │   ├── models/                # Pydantic FHIR R4 models (Patient, Encounter …)
│   │   ├── bundle.py              # Bundle builder
│   │   ├── ndjson.py              # NDJSON reader/writer
│   │   ├── references.py          # reference extractor & validator
│   │   └── tests/
│   │
│   ├── synthetic/                 # deterministic data generator
│   │   ├── config.py              # GenerationConfig pydantic model
│   │   ├── id_factory.py          # deterministic ID minter
│   │   ├── demographics.py        # names, DoB, gender, address
│   │   ├── archetypes/            # clinical scenario templates
│   │   │   ├── base.py
│   │   │   ├── diabetes.py
│   │   │   ├── hypertension.py
│   │   │   ├── healthy.py
│   │   │   └── …
│   │   ├── encounter_gen.py       # encounter + linked resource creation
│   │   ├── pools.py               # shared Practitioner / Organization pool
│   │   ├── registry.py            # in-memory resource + reference registry
│   │   ├── runner.py              # top-level orchestrator
│   │   ├── catalogs/              # curated coding catalogs (YAML/JSON)
│   │   └── tests/
│   │
│   ├── graph/                     # FHIR → graph transform + Neo4j loader
│   │   ├── transformer.py         # FHIR resource → canonical node/edge
│   │   ├── loader.py              # Neo4j MERGE writer
│   │   ├── constraints.py         # Cypher constraint/index DDL
│   │   ├── schema.py              # canonical GraphNode / GraphEdge models
│   │   └── tests/
│   │
│   ├── quality/                   # DQ framework
│   │   ├── rules.py               # individual DQ rule implementations
│   │   ├── runner.py              # run all rules, produce report
│   │   ├── models.py              # DQ report pydantic model
│   │   └── tests/
│   │
│   └── ai/                        # AI query planner
│       ├── intent.py              # NL → intent classification
│       ├── templates.py           # allowlisted Cypher query templates
│       ├── validator.py           # Cypher AST / string safety validator
│       ├── evidence.py            # evidence formatting
│       └── tests/
│
├── pipelines/                     # CLI / script orchestration
│   ├── generate.py                # run synthetic generator
│   ├── validate.py                # run DQ pipeline
│   ├── load_fhir.py               # push to HAPI FHIR
│   ├── build_graph.py             # transform + load into Neo4j
│   ├── reconcile.py               # end-to-end count reconciliation
│   └── run_all.py                 # full pipeline: generate → validate → load → build → reconcile
│
├── migrations/                    # PostgreSQL schema migrations (Alembic)
│
├── references/                    # curated terminology catalogs, coding tables
│   ├── snomed_subset.json
│   ├── loinc_subset.json
│   ├── rxnorm_subset.json
│   └── icd10_subset.json
│
├── artifacts/                     # generated output (git-ignored)
│   ├── bundles/
│   ├── ndjson/
│   └── data_quality_summary.json
│
├── infra/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml     # dev overrides (volumes, hot-reload)
│   ├── neo4j/
│   │   └── neo4j.conf
│   ├── hapi/
│   │   └── application.yaml
│   └── postgres/
│       └── init.sql
│
├── docs/                          # specifications (source of truth)
├── .env.example
├── .gitignore
├── pyproject.toml                 # root: workspace / shared dev deps
├── Makefile                       # convenience targets
└── README.md
```

## Components

### `apps/api`
FastAPI application containing only API and orchestration logic.
No direct data generation or graph transformation lives here — it delegates to `libs/`.

### `apps/web`
Next.js frontend (App Router, TypeScript strict, Tailwind, shadcn/ui, Cytoscape.js).

### `libs/synthetic`
Deterministic synthetic-data generator. Pure Python; no framework dependencies.

### `libs/fhir`
FHIR R4 Pydantic models, serialization, Bundle building, NDJSON I/O, reference extraction and validation.

### `libs/graph`
FHIR-to-graph transformation (canonical node/edge model) and Neo4j MERGE-based loader.

### `libs/quality`
Data-quality rule engine. Runs schema validation, referential integrity, temporal consistency, coded-value checks, and produces a structured report.

### `libs/ai`
Read-only graph query planning: intent classification, Cypher template selection, parameter filling, Cypher safety validation, evidence formatting.

### `pipelines/`
Executable orchestration scripts that compose `libs/` modules:
- `generate` — create synthetic FHIR data
- `validate` — run DQ pipeline
- `load_fhir` — push to HAPI FHIR
- `build_graph` — transform + load into Neo4j
- `reconcile` — count reconciliation across stores
- `run_all` — full pipeline end-to-end

## Container topology (Docker Compose)

```text
┌──────────────────────────────────────────────────────────┐
│  docker-compose.yml                                      │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ postgres │  │  neo4j   │  │ hapi-fhir│  │ api      │ │
│  │  :5432   │  │ :7474    │  │  :8080   │  │  :8000   │ │
│  │          │  │ :7687    │  │          │  │          │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│                                                          │
│  ┌──────────┐                                            │
│  │  web     │                                            │
│  │  :3000   │                                            │
│  └──────────┘                                            │
└──────────────────────────────────────────────────────────┘
```

| Service      | Image / Base          | Ports          | Purpose                          |
|--------------|-----------------------|----------------|----------------------------------|
| `postgres`   | `postgres:16-alpine`  | 5432           | Metadata, DQ, audit, lineage     |
| `neo4j`      | `neo4j:5-community`   | 7474, 7687     | Clinical knowledge graph         |
| `hapi-fhir`  | `hapiproject/hapi`    | 8080           | FHIR R4 server                   |
| `api`        | custom Dockerfile     | 8000           | FastAPI backend                  |
| `web`        | custom Dockerfile     | 3000           | Next.js frontend                 |

## Data layers

### Raw
FHIR R4 JSON/NDJSON, immutable per generation run. Stored in `artifacts/`.

### Validated
FHIR resources that passed structural and referential checks.

### Graph canonical layer
Simple internal schema:

```json
{
  "nodes": [{"id":"Patient/p-000001","type":"Patient","properties":{}}],
  "edges": [{"source":"Patient/p-000001","type":"HAS_ENCOUNTER","target":"Encounter/e-...","properties":{}}]
}
```

### Neo4j
Queryable semantic graph loaded via MERGE/upsert.

### PostgreSQL
- `pipeline_runs` — run ID, status, timestamps, config snapshot
- `data_quality_results` — per-run DQ rule outcomes
- `lineage_mappings` — business term → EDM attribute → FHIR element mapping
- `ingestion_events` — resource-level ingestion audit trail

## Identity strategy
All IDs must be deterministic from:
- global generation seed
- patient sequence
- resource type
- resource sequence

Example:
- `Patient/p-000001`
- `Encounter/p-000001-e-0007`
- `Observation/p-000001-o-0014`

Do not use random UUIDs for primary demo identifiers unless a FHIR Bundle `fullUrl` specifically benefits from `urn:uuid:`.

## Idempotency
- FHIR generation with same seed/config must produce equivalent logical data.
- Ingestion writes use upsert semantics.
- Graph rebuild can be safely rerun.
- Pipeline runs have unique run IDs while data IDs remain stable.

## AI boundary
The LLM may:
- classify intent
- select a query template
- fill validated parameters
- explain returned results

The LLM may not:
- execute arbitrary write Cypher
- infer facts not returned by the graph
- claim clinical causality

## Cross-cutting concerns

### Observability
- Structured JSON logging (structlog) across all Python services
- OpenTelemetry traces: API → Neo4j / PostgreSQL
- Prometheus metrics endpoint on API (`/metrics`)
- Request-ID propagation through all layers

### Configuration
- All services configured via environment variables
- `.env.example` committed; `.env` git-ignored
- Pydantic `BaseSettings` for typed config in Python services
- No secrets in source; no real PHI anywhere
