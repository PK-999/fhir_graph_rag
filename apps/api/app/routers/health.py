"""Health check router."""

from apps.api.app.dependencies import db
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, object]:
    """Return service health status including database connectivity."""
    return {
        "status": "ok",
        "service": "fhirgraph-api",
        "neo4j": db.neo4j_connected,
        "postgres": db.postgres_connected,
    }
