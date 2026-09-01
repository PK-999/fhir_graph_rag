"""FHIRGraph API — FastAPI application factory."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
import structlog
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_fastapi_instrumentator import Instrumentator
from typing import TYPE_CHECKING

from apps.api.app.dependencies import db
from apps.api.app.routers import (
    assistant,
    cohorts,
    dashboard,
    data_quality,
    graph,
    health,
    lineage,
    patients,
    timeline,
)
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Connect to databases on startup; disconnect on shutdown."""
    await db.connect()
    yield
    await db.disconnect()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="FHIRGraph API",
        description="Synthetic healthcare knowledge-graph platform API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:4000", "http://127.0.0.1:4000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request-ID middleware ──
    @app.middleware("http")
    async def add_request_id(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ── Routers ──
    #
    # SECURITY BOUNDARY: All routes below are unauthenticated.
    # This is acceptable ONLY while the system serves synthetic data in a
    # trusted local demonstration.  Before any deployment that introduces
    # real clinical data, multi-tenancy, write APIs, or exposure beyond
    # localhost, add a centralized authentication dependency (e.g. OAuth2
    # bearer / OIDC) and route-level authorization scopes.  Health and
    # readiness endpoints should be the only exemptions.
    #
    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
    app.include_router(patients.router, prefix="/api/v1", tags=["patients"])
    app.include_router(timeline.router, prefix="/api/v1", tags=["timeline"])
    app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
    app.include_router(cohorts.router, prefix="/api/v1", tags=["cohorts"])
    app.include_router(data_quality.router, prefix="/api/v1", tags=["data_quality"])
    app.include_router(lineage.router, prefix="/api/v1", tags=["lineage"])
    app.include_router(assistant.router, prefix="/api/v1", tags=["assistant"])

    # ── Observability ──
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )

    FastAPIInstrumentor.instrument_app(app)
    Instrumentator().instrument(app).expose(app)

    return app


app = create_app()
