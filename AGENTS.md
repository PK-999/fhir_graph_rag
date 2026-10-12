# FHIRGraph contributor context

Build and maintain a local mock-healthcare portfolio: seeded FHIR R4 → HAPI / Neo4j / PostgreSQL → FastAPI / Next.js → grounded, inspectable answers. The default Make demo has 100 patients; the isolated benchmark has 1,000. The graph UI uses React Flow.

Start with README.md and docs/README.md. Read only the current architecture, API or graph contract relevant to the change. docs/archive contains historical plans, not current requirements.

- Use synthetic data only. Keep private environments, credentials, generated datasets and caches untracked.
- Preserve source FHIR fields separately from derived canonical references. Never invent causal edges or successful ingestion evidence.
- Keep question semantics bounded, queries owned and parameterized, and citations exact. Unsupported meaning abstains.
- Keep scripts/evaluate.py independent of the production generator, resolver, planner and query compiler.
- Prefer small typed modules and existing dependencies. Preserve public contracts during cleanup.
- Read apps/web/AGENTS.md before frontend edits. Browser code uses lib/api.ts; server pages use lib/server-api.ts.
- Run focused checks while editing, then make check and make browser-check. For data/API/frontend integration changes, run the selected stack's make demo and make verify-demo.
- Preserve datasets and Docker volumes. Recreating only the web service repairs a stale source mount; see docs/GETTING_STARTED.md. Avoid replacing mounted source directories while dev containers run.
