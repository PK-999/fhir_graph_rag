# Run, verify and recover the demo

## New checkout

Install Python 3.12+, Node.js 22+ and Docker Desktop with Compose. Start Docker before running the application.

```bash
make setup
make demo
make verify-demo
```

`make setup` installs constrained Python dependencies, uses the npm lockfile, installs Chromium and creates a private `.env` with local database credentials. It preserves an existing `.env`. Initial dependencies/images and the production build's Geist fonts need network access.

`make demo` starts five services, generates 100 patients from seed `20260830`, runs eight quality checks, uploads to HAPI, builds the reference graph, reconciles stores and evaluates the query engine. `make verify-demo` additionally runs the real browser walkthrough. Ollama is optional.

| Surface | Default local address |
|---|---|
| Application | http://localhost:4010 |
| API documentation | http://localhost:8010/docs |
| HAPI FHIR | http://localhost:58080/fhir |
| Neo4j Browser | http://localhost:57474 |

## Existing workspace and datasets

The orchestrated pipeline registers one dataset per store. Re-running the same dataset is supported; a new seed, patient count or serialization requires a fresh Compose namespace and output directory. This prevents mixing old and new resources.

The preserved release workspace uses:

```bash
make ENV_FILE=.env.release OUTPUT=artifacts/release-demo demo
make ENV_FILE=.env.release OUTPUT=artifacts/release-demo verify-demo
make ENV_FILE=.env.release down
```

For a new dataset without deleting the previous one, stop its selected stack, copy the private environment to a new private file, set a new `COMPOSE_PROJECT_NAME`, and select a new output directory. Reuse only credentials belonging to that namespace. Keep alternate `FHIRGRAPH_*` host ports consistent with the pipeline service URLs in the same file. `.env.example` shows the available settings.

`ENV_FILE` configures both Compose and pipeline commands. `OUTPUT`, `PATIENTS` and `SEED` select artifacts and the workload, for example:

```bash
make ENV_FILE=.env.study OUTPUT=artifacts/study PATIENTS=250 SEED=42 demo
```

This example requires `.env.study` to be prepared with a fresh namespace first. Generated data, manifests, checkpoints and reports remain ignored by Git.

## Routine commands

| Command | Purpose |
|---|---|
| `make help` | List the supported workflow |
| `make dev` / `make down` | Start or stop the selected stack; stopping retains volumes |
| `make generate` / `make validate` | Generate and independently check artifacts |
| `make pipeline` | Run the audited generation → stores → reconciliation lifecycle |
| `make smoke` / `make evaluate` | Probe readiness or evaluate all 33 cases and exact sources |
| `make check` / `make browser-check` | Run source/build gates or controlled browser regressions |
| `make benchmark` | Measure an isolated 1,000-patient workload and graph replay recovery |
| `make record-demo` | Record the 100-patient UI walkthrough; MP4 export requires ffmpeg |

Use the same `ENV_FILE` and `OUTPUT` arguments throughout a workload. Docker commands preserve volumes unless you explicitly use the destructive `reset-data` target. `make clean` removes source caches; it preserves generated datasets.

## Optional local model

The deterministic question catalog works without a model. To try exact cited-fact selection, run an existing local Ollama model and set `LLM_MODEL` in the selected private environment to that installed model's name. Compose connects to the host through `host.docker.internal`; a host-run API uses `LLM_BASE_URL` directly. Enable **Select cited facts with the local model** in the question explorer.

Model output must select exact resource/field/value triples from bounded candidates. Invalid values/types, extra keys, prose and invented facts are rejected; unavailable/rejected output preserves retrieval. `use_model:true` is an experimental planner mode accepted only when it agrees with the complete supported deterministic parse.

## Troubleshooting

**Docker is unavailable:** start Docker Desktop and rerun `make dev`. Read the first failing service's logs rather than resetting its volumes.

**Ports are occupied:** stop the other selected stack or choose a new, internally consistent set of host ports in the private environment. Set the corresponding Make API/web port overrides for smoke/evaluation/browser commands.

**Layout/module file exists on the host but is missing in Docker:** replacing a source directory during a branch switch can leave a bind mount attached to its old directory. Recreate only the frontend and refresh the browser:

```bash
make ENV_FILE=.env.release restart-web
```

**Dataset binding is rejected:** use the original workload and persistent store, or create a fresh namespace/output. Do not replace a lost credential file for an existing benchmark volume; its original binding must be retained.

**Store contents changed manually or were replaced:** checkpoints are confirmations of prior writes, not a live integrity probe. With the correct private environment selected, standalone `pipelines.load_fhir` and `pipelines.build_graph` support explicit `--no-resume` idempotent replay, followed by `pipelines.reconcile --graph`. They bypass the orchestrator's single-dataset guard; keep them on the intended dataset/store. Never infer that a different dataset is safe to merge because replay succeeded.

**An API dependency is unavailable:** inspect `/api/v1/health/ready` and the selected Compose logs. The readiness probe checks Neo4j, PostgreSQL and HAPI. Full browser verification checks the actual page and evidence flow beyond basic HTTP readiness.

## What “ready” means

The project is an end-to-end local mock-data portfolio with repeatable checks. The public static site showcases captured evidence, while the application and stores run in Docker. Full FHIR profile/invariant/terminology conformance, clinical use, authentication for public healthcare APIs, unrestricted semantic search and production load guarantees are separate future projects.
