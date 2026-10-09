# Current architecture

The portfolio demo follows synthetic FHIR resources through independent validation, persistent FHIR storage, an explicit-reference graph, constrained retrieval, and source-backed answers. See [README](../README.md) for setup and the walkthrough.

## Data and audit flow

`libs/synthetic` writes deterministic transaction bundles, per-type NDJSON, a SHA-256 manifest, and a quality report. `libs/quality` independently validates serialized artifacts. `pipelines.run_all` holds a PostgreSQL advisory lock, records a unique run and non-secret configuration, and executes generation → validation → HAPI upload → graph loading → reconciliation.

Eight rule outcomes and failure details are persisted to PostgreSQL. A complete successful ingestion stage records `upserted` events per resource; a failed stage records a failed run and does not invent successful events for that stage. Reconciliation compares HAPI counts and exact Neo4j node/reference identities. A different registered dataset is rejected before either store is changed. Started ingestion attempts are considered when guarding later runs because they may have partially written data. A refusal before ingestion is marked `blocked`, so it cannot prevent a valid same-dataset rerun.

HAPI uses PostgreSQL's `hapi` schema, keeping exact source resources across container restarts. The application's run, quality, ingestion, and mapping tables use `public`. Initialization SQL runs for fresh volumes. Existing older PostgreSQL volumes need the `hapi` schema created before enabling this configuration; the verified demo uses fresh isolated volumes.

## Graph contract

`ResourceType/id` is the canonical identity. Each resource is a node labeled by type. Nested FHIR fields flatten into snake_case properties with positional array indices. Explicit local FHIR references become directed edges; original extra source JSON fields survive transformation. Top-level narrative is excluded from graph properties.

The builder checks resource types, IDs, duplicate identities, and complete reference closure before opening Neo4j. A compact index explicitly resolves relative/same-service references. Bundle validation can also resolve fullUrl aliases/URNs within Bundle context; the NDJSON graph builder has no Bundle alias map and diagnoses URNs rather than guessing targets. Contained references are preserved without invented top-level edges. External/unresolved/versioned references are diagnosed. Original literal fields remain distinct from canonical association properties. Load errors propagate and drivers close. Per-resource ID constraints support indexed edge endpoint lookups; writes use batches of 500 and `MERGE`. Sharing an encounter never creates a causal `SUPPORTED_BY` edge.

Input is disk-spooled after full structural/identity preflight. Graph transformation and loading use bounded batches; FHIR uploads retain bounded tasks. Atomic content-bound checkpoints record confirmed batches, and stage-complete audit events retain source hashes/locations. There is no whole-run rollback or deletion of older resources. The full orchestration enforces a single registered dataset; standalone loaders bypass that guard. External/manual store changes require reconciliation.

## Grounded question flow

1. The API accepts a supported natural-language question or a strict `QueryPlan`.
2. `libs/rag/plans.py` recognizes complete advertised questions and rejects unsupported filters instead of dropping them.
3. `libs/rag/queries.py` chooses an application-owned parameterized template. User/model text never becomes executable Cypher.
4. Neo4j returns canonical patient/resource IDs and clinical source fields in stable order, with one lookahead row for pagination.
5. `libs/rag/evidence.py` formats a limited-result answer and exact FHIR field citations.
6. The frontend presents results and uses `/resources/{type}/{id}` to inspect the source resource through a bounded HAPI proxy.

Supported intents are patient listing, condition cohorts, medication cohorts, patient/lab histories, and latest labs with an active medication request. Latest lab selection uses final/amended/corrected observations and UTC epoch seconds plus nanoseconds, followed by descending canonical ID for ties. Threshold/unit filtering happens after selecting the latest observation; missing values never fall back to an older high result. Duplicate medication matches select one deterministic request.

History follows standard subject references and AllergyIntolerance patient references, removes duplicate resource matches, and returns up to 20 records by default or 100 per page. Resource-specific recorded dates determine chronological order; undated records follow, with ascending canonical IDs breaking ties. The date and patient reference are cited by their exact source fields. Recorded date fields describe different events and do not imply treatment administration or causation.

All six assistant intents accept a transport-level offset independently of the strict clinical plan. Owned queries use `SKIP` and a `limit + 1` fetch. Only the requested rows enter evidence and answers; response pagination identifies the next offset or the end of the result set. The frontend continues with the original question and explicit plan, appends rows, and merges evidence by canonical ID. Invalid, repeated, changed-plan, empty, or failed continuation pages retain previously loaded results for retry. This is offset pagination over a registered dataset, not a snapshot under concurrent store changes. The separate cohort builder and patient detail projections retain their own bounded contracts.

The optional local Ollama planner must agree with a complete supported deterministic parse. Optional `use_summary_model` selects typed candidate facts, validated exactly against retrieved graph evidence and rendered by the application. Unavailable/rejected selection preserves retrieval. Live FHIR validation is performed separately by the evaluator or source inspection; unrestricted model prose is never an answer. There is no vector index.

## UI and runtime

FastAPI exposes graph/patient/timeline/cohort queries, actual quality results, a static mapping catalog, the question engine, and source retrieval. Next.js server pages use `API_INTERNAL_URL`; browser requests use `NEXT_PUBLIC_API_URL`. The patient FHIR tab displays the exact HAPI Patient resource. Failed services show unavailable states rather than mock successful runs. Scripted clinical narratives and speculative edge insights were removed; graph type highlighting is explicitly labeled as highlighting. Patient overview grouping edges are identified separately from explicit FHIR references.

Compose runs five local services. API readiness probes Neo4j, PostgreSQL, and HAPI with bounded timeouts; web startup depends on that real readiness check. HAPI's distroless image does not have a fake JVM-only healthcheck. Ollama is optional and runs separately.

Independent `scripts/evaluate.py` reads raw NDJSON without importing the retrieval/compiler code, derives complete expected result and evidence sets, and compares 33 live API cases across all supported intents. It checks the first plan against an independently declared plan, verifies every page boundary and displayed fact, traverses all expected pages, and compares the combined ordered set. It preserves nanosecond precision in its independent date ordering and rejects unsupported-filter interpretations. The oracle bounds traversal, so incorrect metadata cannot create an infinite loop. Its report retains actual pages plus combined results; it has no 100-patient cap, though input and expectations are still held in memory. Each distinct cited resource is fetched once through the bounded source proxy; identity, patient association, and cited fields must match. This checks the retrieved evidence subset, not every upstream FHIR field or resource. Controlled browser regressions cover failures, zero matches, evidence inspection, history pagination/retry/reset, cohorts, and graph expansion; `make verify-demo` combines readiness, independent evaluation, and the live walkthrough.

## Resume and provenance boundaries

Checkpoint bindings cover source content, dataset, sanitized destination/principal, transformer version and batch partition. They assume the existing persistent store is unchanged. Store replacement or manual drift requires explicit idempotent `--no-resume` replay and reconciliation; confirmations are not a live hash probe. Resource provenance reports stage-confirmed artifact hashes/locations and retains run outcomes, including successful stages in a later failed run. Legacy rows remain nullable; API requests against an older unmigrated schema report unavailable provenance.
