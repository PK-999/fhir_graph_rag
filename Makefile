.PHONY: dev down infra lint test generate pipeline clean

# ── Docker ──
dev:
	docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up --build

down:
	docker compose -f infra/docker-compose.yml -f infra/docker-compose.dev.yml down -v

infra:
	docker compose -f infra/docker-compose.yml up -d postgres neo4j hapi-fhir

# ── Lint & Type Check ──
lint:
	ruff check libs/ apps/ pipelines/
	ruff format --check libs/ apps/ pipelines/
	mypy libs/ apps/ pipelines/

format:
	ruff check --fix libs/ apps/ pipelines/
	ruff format libs/ apps/ pipelines/

# ── Tests ──
test:
	pytest libs/ apps/ -v --tb=short

test-cov:
	pytest libs/ apps/ -v --tb=short --cov=libs --cov=apps --cov-report=html

# ── Synthetic Data Generation ──
PATIENTS ?= 20
SEED ?= 20260830

generate:
	python -m pipelines.generate --patients $(PATIENTS) --seed $(SEED)

validate:
	python -m pipelines.validate --input artifacts/

# ── Full Pipeline ──
pipeline:
	python -m pipelines.run_all --patients $(PATIENTS) --seed $(SEED)

# ── Cleanup ──
clean:
	rm -rf artifacts/bundles artifacts/ndjson artifacts/data_quality_summary.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
