# syntax=docker/dockerfile:1

# ── Base ──
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements.lock README.md ./
COPY libs libs
COPY pipelines pipelines
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/api/__init__.py apps/api/__init__.py
COPY apps/api/app apps/api/app
RUN pip install --no-cache-dir -c requirements.lock -e . -e apps/api

# ── Dev target (hot-reload) ──
FROM base AS dev
COPY . .
EXPOSE 8000
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production target ──
FROM base AS prod
RUN useradd --create-home --uid 10001 fhirgraph
USER fhirgraph
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=2)"]
CMD ["uvicorn", "apps.api.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
