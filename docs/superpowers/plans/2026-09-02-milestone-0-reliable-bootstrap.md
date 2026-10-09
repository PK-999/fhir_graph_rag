# Milestone 0 Reliable Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one documented command start the complete FHIRGraph development stack and make API/web liveness, dependency readiness, lint, typing, tests, builds, and CI truthful and reproducible.

**Architecture:** Retain the existing modular monorepo and Compose topology. Separate process liveness from real dependency readiness, make host ports configurable, add the missing production-grade web container, and make local and CI commands call the same quality gates.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, asyncpg, Neo4j async driver, pytest, Ruff, mypy, Next.js 16.3.3, React 19, TypeScript, ESLint, Docker Compose, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-01-fhirgraph-finish-line-design.md`

## Global Constraints

- Scope is a polished synthetic-data research/portfolio platform; do not add real-PHI or regulated-production features.
- Reference deployment is one workstation with local Ollama and replaceable adapters.
- Preserve all pre-existing frontend changes; `apps/web` is a dirty nested Git repository on `main`.
- The workspace root is not a Git repository. Do not create commits or alter nested Git metadata during this milestone.
- Do not print or rewrite `.env`; use `.env.example` and safe presence checks only.
- Configuration changes are verified by executing their consumers, not by grepping source text.
- Every production behavior change follows red-green-refactor.
- The supported containerized Next.js build uses standalone output.
- Direct-Chrome UX verification remains a later release gate; Milestone 0 verifies the web health surface and startup behavior.

---

### Task 1: Truthful API liveness and readiness

**Files:**
- Modify: `apps/api/app/config.py`
- Modify: `apps/api/app/dependencies.py`
- Modify: `apps/api/app/routers/health.py`
- Modify: `apps/api/tests/test_health.py`

**Interfaces:**
- Produces: `DatabaseConnections.readiness() -> DependencyReadiness`
- Produces: `GET /api/v1/health/live`
- Produces: `GET /api/v1/health/ready`
- Preserves: `GET /api/v1/health` as a readiness-compatible endpoint

- [x] **Step 1: Write failing endpoint tests**

Add tests that override the database readiness result and assert literal contracts:

```python
def test_liveness_does_not_claim_dependency_health(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "fhirgraph-api"}


def test_readiness_returns_503_when_neo4j_is_unreachable(client: TestClient) -> None:
    db.set_readiness_for_test(neo4j=False, postgres=True, hapi=True)
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["neo4j"]["ready"] is False
```

Keep test-only readiness substitution in a pytest fixture/monkeypatch rather than adding a production-only test hook.

- [x] **Step 2: Run the health tests and verify RED**

Run: `.venv/bin/pytest apps/api/tests/test_health.py -q`

Expected: FAIL because `/health/live`, `/health/ready`, and real readiness checks do not exist.

- [x] **Step 3: Implement typed readiness checks**

Add typed dependency results and bounded checks:

```python
@dataclass(frozen=True)
class DependencyStatus:
    ready: bool
    detail: str | None = None


@dataclass(frozen=True)
class DependencyReadiness:
    neo4j: DependencyStatus
    postgres: DependencyStatus
    hapi: DependencyStatus

    @property
    def ready(self) -> bool:
        return self.neo4j.ready and self.postgres.ready and self.hapi.ready
```

`DatabaseConnections.readiness()` must execute `RETURN 1`, `SELECT 1`, and `GET {hapi_fhir_url}/metadata` with `asyncio.timeout(settings.readiness_timeout_seconds)`. A driver or pool object existing is not evidence of readiness.

- [x] **Step 4: Implement liveness/readiness routes**

Return HTTP 200 from liveness. Return HTTP 200 or 503 from readiness based on the typed result. Keep `/health` as the same truthful readiness response for compatibility.

- [x] **Step 5: Run focused and full API tests**

Run: `.venv/bin/pytest apps/api/tests/test_health.py -q`

Expected: PASS.

Run: `.venv/bin/pytest apps/api/tests -q`

Expected: PASS.

---

### Task 2: Executable Compose and container contracts

**Files:**
- Create: `apps/web/Dockerfile`
- Create: `.dockerignore`
- Modify: `apps/api/Dockerfile`
- Modify: `apps/web/next.config.ts`
- Modify: `infra/docker-compose.yml`
- Modify: `infra/docker-compose.dev.yml`
- Modify: `.env.example`
- Create: `tests/test_bootstrap_contract.py`

**Interfaces:**
- Produces: `docker compose --env-file .env.example ... config`
- Produces: API and web container health checks
- Produces: configurable `FHIRGRAPH_*_PORT` host bindings

- [x] **Step 1: Write the failing bootstrap contract test**

```python
def test_compose_configuration_is_renderable() -> None:
    result = subprocess.run(
        [
            "docker", "compose", "--env-file", ".env.example",
            "-f", "infra/docker-compose.yml",
            "-f", "infra/docker-compose.dev.yml",
            "config", "--quiet",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_web_image_can_be_built_from_declared_dockerfile() -> None:
    compose = render_compose_config()
    assert compose["services"]["web"]["build"]["dockerfile"] == "apps/web/Dockerfile"
    assert (ROOT / "apps/web/Dockerfile").is_file()
```

- [x] **Step 2: Run the bootstrap contract and verify RED**

Run: `.venv/bin/pytest tests/test_bootstrap_contract.py -q`

Expected: FAIL because `apps/web/Dockerfile` is missing and the full development contract is not renderable/buildable.

- [x] **Step 3: Add standalone Next.js output and web image**

Set `output: "standalone"` in `next.config.ts`. Build the image with dependency, builder, development, and non-root production stages. Copy `.next/standalone`, `.next/static`, and `public` into the production stage.

- [x] **Step 4: Repair the API image**

Copy package sources before installing the editable API package, use a non-root production user, and add a container health check against `/api/v1/health/live`.

- [x] **Step 5: Make host ports collision-safe and explicit**

Use these environment-backed defaults:

```text
FHIRGRAPH_WEB_PORT=4010
FHIRGRAPH_API_PORT=8010
FHIRGRAPH_POSTGRES_PORT=55432
FHIRGRAPH_NEO4J_HTTP_PORT=57474
FHIRGRAPH_NEO4J_BOLT_PORT=57687
FHIRGRAPH_HAPI_PORT=58080
```

Bind stateful services to `127.0.0.1`. Container-to-container URLs continue to use service names and internal ports.

- [x] **Step 6: Add API and web health checks and dependency conditions**

The API must depend on healthy PostgreSQL, Neo4j, and HAPI. The web must depend on healthy API. Health checks must use container-local endpoints.

- [x] **Step 7: Run executable configuration checks**

Run: `.venv/bin/pytest tests/test_bootstrap_contract.py -q`

Expected: PASS.

Run: `docker compose --env-file .env.example -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config --quiet`

Expected: exit 0.

---

### Task 3: One-command developer and CI quality surface

**Files:**
- Modify: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `apps/web/package.json`
- Modify: `apps/web/playwright.config.ts`

**Interfaces:**
- Produces: `make dev`, `make infra`, `make check`, `make smoke`, `make down`
- Produces: `npm run typecheck`, `npm run test:e2e`, and deterministic webpack container build

- [x] **Step 1: Add command-level contract assertions**

Extend `tests/test_bootstrap_contract.py` to execute `make -n check`, `make -n dev`, and `make -n smoke` and assert exit 0. This catches missing targets or malformed Make recipes without starting services.

- [x] **Step 2: Run the focused test and verify RED**

Run: `.venv/bin/pytest tests/test_bootstrap_contract.py -q`

Expected: FAIL because `check` and `smoke` targets are missing.

- [x] **Step 3: Implement the Makefile surface**

`make check` runs Python lint/format/type/tests and frontend lint/type/build. `make smoke` renders Compose config, checks API liveness/readiness, and checks the web root using configured ports. `make down` preserves volumes by default; a separate explicit `make reset-data` performs destructive volume removal.

- [x] **Step 4: Align package scripts and CI**

Use these scripts:

```json
{
  "typecheck": "tsc --noEmit",
  "build": "next build --webpack",
  "test:e2e": "playwright test"
}
```

CI runs Compose configuration validation, Python quality gates, frontend quality gates, and builds both images. It uses `.env.example` without exposing secrets.

- [x] **Step 5: Rewrite Quick Start around the verified commands**

Document port defaults, safe `.env` creation, `make dev`, `make smoke`, `make check`, `make down`, and the difference between liveness and readiness. Do not claim the full data pipeline is loaded by Milestone 0.

- [x] **Step 6: Run command contracts**

Run: `.venv/bin/pytest tests/test_bootstrap_contract.py -q`

Expected: PASS.

---

### Task 4: Python quality baseline

**Files:**
- Modify: Python files reported by Ruff or mypy under `apps/`, `libs/`, and `pipelines/`
- Modify: `pyproject.toml` only for accurate third-party typing overrides

**Interfaces:**
- Produces: clean `ruff check`, `ruff format --check`, and strict `mypy`

- [x] **Step 1: Capture the existing RED gates**

Run: `.venv/bin/ruff check apps libs pipelines`

Expected baseline: nonzero with 35 findings.

Run: `.venv/bin/mypy apps libs pipelines`

Expected baseline: nonzero with 100 errors in 39 files.

- [x] **Step 2: Apply safe Ruff fixes and formatting**

Run: `.venv/bin/ruff check --fix apps libs pipelines`

Run: `.venv/bin/ruff format apps libs pipelines`

Review every non-mechanical remaining finding and patch it explicitly.

- [x] **Step 3: Fix typing at source by subsystem**

Use `dict[str, Any]` and typed nested helpers in FHIR/graph code; type archetype state distinctly from booleans; annotate router dependencies and async generators; use SQLAlchemy 2 `DeclarativeBase` and `Mapped`; add the correct asyncpg missing-import override; and make optional Ollama response content explicit.

- [x] **Step 4: Re-run narrow subsystem checks after each group**

Run mypy separately for `libs/fhir`, `libs/synthetic`, `libs/graph`, `apps/api`, and `pipelines` until each returns exit 0.

- [x] **Step 5: Run the full Python gate**

Run: `.venv/bin/ruff check apps libs pipelines`

Expected: PASS with no findings.

Run: `.venv/bin/ruff format --check apps libs pipelines`

Expected: PASS.

Run: `.venv/bin/mypy apps libs pipelines`

Expected: PASS with no errors.

Run: `.venv/bin/pytest libs apps tests -q`

Expected: PASS.

---

### Task 5: Frontend quality baseline

**Files:**
- Modify: `apps/web/src/app/patients/page.tsx`
- Modify: frontend files with reported unused imports
- Modify: `apps/web/eslint.config.mjs` only if a rule conflicts with an intentional documented framework pattern

**Interfaces:**
- Produces: clean ESLint, TypeScript, and production build

- [x] **Step 1: Re-run the current RED gate**

Run: `npm run lint`

Working directory: `apps/web`

Expected: FAIL because `SortHeader` is created during render, plus reported warnings.

- [x] **Step 2: Move sortable header rendering to a stable module-level component or pure function**

Pass the resolved sort state and generated link as props. Remove unused imports and variables without changing visible behavior.

- [x] **Step 3: Run frontend gates**

Run: `npm run lint`

Expected: PASS with no warnings.

Run: `npm run typecheck`

Expected: PASS.

Run: `npm run build`

Expected: PASS using webpack.

---

### Task 6: Full-stack smoke verification and evidence

**Files:**
- Modify: `docs/FINISH_LINE_TRACKER.md`
- Modify: `docs/BUILD_PLAN.md`
- Create: `docs/evidence/milestone-0-verification.md`

**Interfaces:**
- Produces: requirement-by-requirement Milestone 0 evidence

- [x] **Step 1: Verify static quality gates fresh**

Run: `make check`

Expected: exit 0 with Python and frontend gates passing.

- [x] **Step 2: Verify Compose configuration and image builds**

Run: `docker compose --env-file .env.example -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config --quiet`

Expected: exit 0.

Run: `docker compose --env-file .env.example -f infra/docker-compose.yml build api web`

Expected: exit 0.

- [x] **Step 3: Start the stack and wait on declared health checks**

Run: `make dev`

Observe the live Compose process. Do not replace a running handle after an observation timeout.

- [x] **Step 4: Verify liveness, readiness, and web behavior**

Run: `make smoke`

Expected: API liveness 200, API readiness 200 with all declared dependencies ready, and web root 200.

- [x] **Step 5: Verify degraded readiness**

Stop Neo4j only, then request readiness.

Expected: liveness remains 200; readiness becomes 503 and names Neo4j as unavailable. Restart Neo4j and verify readiness returns 200.

- [x] **Step 6: Record evidence and synchronize trackers**

Record exact commands, dates, exit codes, service URLs, health payloads, and any accepted limitations. Mark Milestone 0 complete only if every exit criterion has direct evidence.
