.PHONY: setup dev down reset-data infra compose-check lint web-check browser-check check verify-demo test test-cov smoke generate validate pipeline evaluate demo clean format benchmark record-demo

PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
ENV_FILE ?= .env
export FHIRGRAPH_ENV_FILE := $(ENV_FILE)
COMPOSE = docker compose --env-file $(ENV_FILE) -f infra/docker-compose.yml -f infra/docker-compose.dev.yml
FHIRGRAPH_API_PORT ?= 8010
FHIRGRAPH_WEB_PORT ?= 4010

# ── Docker ──
setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install -c requirements.lock -e '.[dev]' -e apps/api
	npm --prefix apps/web ci
	cd apps/web && npx playwright install chromium
	.venv/bin/python scripts/init_env.py

dev:
	test -f $(ENV_FILE) || (echo "Missing $(ENV_FILE); copy .env.example to .env" && exit 1)
	$(COMPOSE) up --build --detach --wait --wait-timeout 180

down:
	$(COMPOSE) down

reset-data:
	$(COMPOSE) down --volumes

infra:
	test -f $(ENV_FILE) || (echo "Missing $(ENV_FILE); copy .env.example to .env" && exit 1)
	$(COMPOSE) up --detach --wait postgres neo4j hapi-fhir

compose-check:
	docker compose --env-file .env.example -f infra/docker-compose.yml -f infra/docker-compose.dev.yml config --quiet

# ── Lint & Type Check ──
lint:
	$(PYTHON) -m ruff check libs apps pipelines scripts tests
	$(PYTHON) -m ruff format --check libs apps pipelines scripts tests
	$(PYTHON) -m mypy libs apps pipelines scripts

web-check:
	npm --prefix apps/web run lint
	npm --prefix apps/web run typecheck
	npm --prefix apps/web run test:unit
	npm --prefix apps/web run build

check: compose-check lint test web-check

format:
	$(PYTHON) -m ruff check --fix libs apps/api pipelines tests
	$(PYTHON) -m ruff format libs apps/api pipelines tests

# ── Tests ──
test:
	$(PYTHON) -m pytest libs apps tests -v --tb=short

test-cov:
	$(PYTHON) -m pytest libs apps tests -v --tb=short --cov=libs --cov=apps --cov-report=html

smoke:
	$(PYTHON) scripts/smoke.py --api-url http://127.0.0.1:$(FHIRGRAPH_API_PORT)/api/v1 --web-url http://127.0.0.1:$(FHIRGRAPH_WEB_PORT)

# ── Synthetic Data Generation ──
PATIENTS ?= 100
SEED ?= 20260830
OUTPUT ?= artifacts/demo

generate:
	$(PYTHON) -m pipelines.generate --patients $(PATIENTS) --seed $(SEED) --output $(OUTPUT)

validate:
	$(PYTHON) -m pipelines.validate --input $(OUTPUT)

# ── Full Pipeline ──
pipeline:
	$(PYTHON) -m pipelines.run_all --patients $(PATIENTS) --seed $(SEED) --output $(OUTPUT)

evaluate:
	$(PYTHON) scripts/evaluate.py --input $(OUTPUT) --api-url http://127.0.0.1:$(FHIRGRAPH_API_PORT)/api/v1 --output $(OUTPUT)/evaluation.json

browser-check:
	PLAYWRIGHT_PORT=4317 npm --prefix apps/web run test:e2e -- tests/e2e/assistant.spec.ts tests/e2e/graph.spec.ts tests/e2e/cohorts.spec.ts --reporter=line

verify-demo:
	$(MAKE) smoke
	$(MAKE) evaluate
	LIVE_DEMO=1 PLAYWRIGHT_PORT=$(FHIRGRAPH_WEB_PORT) NEXT_PUBLIC_API_URL=http://localhost:$(FHIRGRAPH_API_PORT)/api/v1 npm --prefix apps/web run test:e2e -- tests/e2e/demo.spec.ts --reporter=line

demo:
	$(MAKE) dev
	$(MAKE) pipeline
	$(MAKE) smoke
	$(MAKE) evaluate

# ── Cleanup ──
clean:
	rm -rf artifacts/bundles artifacts/ndjson artifacts/data_quality_summary.json artifacts/dataset_manifest.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

# Isolated measured release workload; all volumes are retained.
benchmark:
	$(PYTHON) scripts/benchmark.py --patients 1000 --seed $(SEED) --output artifacts/release-scale --verify-recovery

record-demo:
	node scripts/record_demo.mjs
