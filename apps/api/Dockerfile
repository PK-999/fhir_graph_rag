# syntax=docker/dockerfile:1

# ── Base ──
FROM python:3.12-slim AS base
WORKDIR /app
COPY pyproject.toml .
COPY apps/api/pyproject.toml apps/api/
RUN pip install --no-cache-dir -e apps/api

# ── Dev target (hot-reload) ──
FROM base AS dev
COPY . .
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production target ──
FROM base AS prod
COPY . .
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
