"""Health check router."""

from typing import Any

from apps.api.app.dependencies import db
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Report that the API process can serve requests."""
    return {"status": "ok", "service": "fhirgraph-api"}


def _readiness_payload(readiness: Any) -> dict[str, object]:
    return {
        "status": "ok" if readiness.ready else "degraded",
        "service": "fhirgraph-api",
        "dependencies": {
            name: {"ready": status.ready, "detail": status.detail}
            for name, status in readiness.dependencies.items()
        },
    }


async def _readiness_response() -> JSONResponse:
    readiness = await db.readiness()
    return JSONResponse(
        status_code=200 if readiness.ready else 503,
        content=_readiness_payload(readiness),
    )


@router.get("/health/ready")
async def readiness() -> JSONResponse:
    """Report real connectivity to every required dependency."""
    return await _readiness_response()


@router.get("/health")
async def health_check() -> JSONResponse:
    """Preserve the original path with truthful readiness semantics."""
    return await _readiness_response()
