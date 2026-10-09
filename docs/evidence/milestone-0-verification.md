# Milestone 0 Verification and Decision Record

**Verified:** 2026-09-02
**Scope:** reliable repository bootstrap and development baseline
**Result:** passed; direct-Chrome visual verification remains a later release gate

## Outcome

FHIRGraph now has one reproducible command that builds and starts PostgreSQL, Neo4j, HAPI FHIR, FastAPI, and Next.js, waits for the real application data path, and exposes the application on collision-safe localhost ports. Static quality gates, executable configuration tests, live health checks, failure-mode behavior, and recovery were verified on the development workstation.

## Changes and reasoning

### Truthful health semantics

- Added `GET /api/v1/health/live` for process liveness.
- Added `GET /api/v1/health/ready` for bounded Neo4j, PostgreSQL, and HAPI FHIR probes.
- Kept `GET /api/v1/health` as a readiness-compatible route so existing callers do not receive a false success.
- Added typed `DependencyStatus` and `DependencyReadiness` models and a configurable probe timeout.
- Closed a failed Neo4j driver during startup instead of retaining a misleading connection object.

Reasoning: the former endpoint treated initialized client objects as proof that databases were available. Separating liveness from readiness prevents an orchestrator, developer, or future agent from sending work into a process whose required data path is unavailable.

### Reliable container topology

- Added development and non-root production stages for the API image.
- Added development, builder, and non-root standalone production stages for the web image.
- Enabled Next.js standalone output and made webpack the explicit supported build path.
- Added a root `.dockerignore` to keep build contexts deterministic and small.
- Added healthchecks and dependency ordering for all application services.
- Corrected the HAPI probe after live verification showed that the current upstream image is distroless and has no `/bin/sh` or `curl`. Its local JVM viability check is intentionally complemented by the API's authoritative HTTP request to `/fhir/metadata`; the web service cannot start until that API readiness check succeeds.

Reasoning: Compose's `service_started` state is not readiness. The transitive chain—dependency viability, API data-path readiness, then web readiness—makes `make dev` return only after the usable platform surface exists.

### Collision-safe configuration

Default host bindings are now:

| Surface | Host port |
|---|---:|
| Web | 4010 |
| API | 8010 |
| PostgreSQL | 55432 |
| Neo4j HTTP | 57474 |
| Neo4j Bolt | 57687 |
| HAPI FHIR | 58080 |

Stateful services bind to `127.0.0.1`; service-to-service traffic remains on the private Compose network. All defaults are overrideable through `.env`.

Reasoning: ports 3000 and 8000 were already occupied by unrelated projects during discovery. Namespaced defaults eliminate ambiguous browser results and reduce accidental exposure of development databases.

### Unified local and CI contracts

- `make dev` builds, starts, and waits for the complete stack.
- `make smoke` verifies API liveness, API readiness, and the web root.
- `make check` verifies Compose configuration, Ruff, formatting, strict mypy, pytest, ESLint, TypeScript, and the production web build.
- `make down` preserves data; the deliberately destructive operation is named `make reset-data`.
- GitHub Actions mirrors the Python, frontend, Compose, and image-build gates.
- The README now documents the verified commands, ports, and health meanings without claiming that a synthetic dataset is already loaded.

Reasoning: a milestone is reproducible only when local development and CI invoke the same executable contracts. Separating normal shutdown from volume deletion makes the common path recoverable.

### Quality repairs

- Removed frontend render-time component creation and unused imports.
- Made API-backed Next.js pages explicitly dynamic, eliminating noisy failed prerender attempts during production builds.
- Parameterized FHIR and graph dictionary types and typed nested transformation helpers.
- Typed synthetic archetype ID factories and state values.
- Migrated metadata models to SQLAlchemy 2 `DeclarativeBase`, `Mapped`, and `mapped_column`.
- Annotated FastAPI async dependencies and guarded optional local-model response content.
- Retained strict mypy settings; only missing third-party type metadata for asyncpg/Neo4j/httpx is scoped through module-specific overrides.

Reasoning: these changes turn the quality commands into enforceable gates without hiding project errors behind broad exclusions.

## Verification evidence

### Static and build gates

Command: `make check`

- Compose model: valid.
- Ruff check: passed.
- Ruff format check: passed.
- Strict mypy: `Success: no issues found in 78 source files`.
- Pytest: passed (55 tests after the final bootstrap contracts were added).
- ESLint: passed with `--max-warnings=0`.
- TypeScript: passed.
- Next.js webpack production build: passed.

Command: `make dev`

- API and web images built successfully.
- PostgreSQL, Neo4j, HAPI FHIR, API, and web containers reached `healthy`.
- Command exited 0 only after declared health dependencies passed.

### Live happy path

Command: `make smoke`

```text
api-liveness: ok
api-readiness: ok
web: ok
```

Readiness payload:

```json
{
  "status": "ok",
  "service": "fhirgraph-api",
  "dependencies": {
    "neo4j": {"ready": true, "detail": null},
    "postgres": {"ready": true, "detail": null},
    "hapi": {"ready": true, "detail": null}
  }
}
```

Observed local request times after warm startup:

- web root: HTTP 200 in approximately 0.082 seconds;
- API readiness: HTTP 200 in approximately 0.053 seconds.

These are smoke observations, not the 100,000-patient benchmark; formal load and latency percentiles belong to Stage 7.

### Live degraded path and recovery

Neo4j was stopped while the API remained running.

- liveness remained HTTP 200;
- readiness returned HTTP 503;
- readiness reported Neo4j as `ServiceUnavailable` while PostgreSQL and HAPI stayed ready.

Neo4j was restarted and `make smoke` returned all three checks to `ok`, demonstrating recovery without rebuilding or deleting data.

## Accepted limitation

The user-enabled Chrome extension is installed and configured, but direct Chrome control from this chat still fails before tab creation with a trusted-browser-session error. No alternate browser was substituted because Chrome was explicitly requested. Visual journeys, console inspection, narrow-width behavior, keyboard/accessibility checks, and accepted screenshots remain explicitly tracked in Stage 8. Network, container, server-rendering, and HTTP checks are complete for Milestone 0.

## Milestone 0 exit criteria

| Criterion | Evidence | Status |
|---|---|---|
| Monorepo structure | existing `apps`, `libs`, `pipelines`, `infra` layout | passed |
| Docker Compose | executable render, builds, and five healthy services | passed |
| Environment example | collision-safe `.env.example` consumed by tests and CI | passed |
| Lint/test commands | `make check` exit 0 | passed |
| CI skeleton | Python, frontend, and container jobs | passed |
| One command starts dependencies | `make dev` exit 0 after health waits | passed |
| API and web health work | live smoke and degraded/recovery evidence | passed |
