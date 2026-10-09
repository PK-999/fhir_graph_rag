"""Lineage API router."""

from typing import Any

import asyncpg
from apps.api.app.dependencies import get_pg_pool
from apps.api.app.routers.resources import SUPPORTED_TYPES
from fastapi import APIRouter, Depends, HTTPException, Path

router = APIRouter(prefix="/lineage")


@router.get("")
async def get_lineage_mappings(pool: Any = Depends(get_pg_pool)) -> dict[str, Any]:
    """Get all lineage mappings from PostgreSQL."""
    query = """
    SELECT business_domain, business_entity, business_attribute, fhir_resource_type as fhir_resource, fhir_element, description
    FROM lineage_mappings
    """
    async with pool.acquire() as conn:
        mappings = await conn.fetch(query)

    return {"mappings": [dict(m) for m in mappings]}


@router.get("/resources/{resource_type}/{resource_id}")
async def get_resource_provenance(
    resource_type: str,
    resource_id: str = Path(pattern=r"^[A-Za-z0-9.-]{1,64}$"),
    pool: Any = Depends(get_pg_pool),
) -> dict[str, Any]:
    """Expose confirmed artifact-to-store events, with a bounded audit history."""
    if resource_type not in SUPPORTED_TYPES:
        raise HTTPException(status_code=404, detail="Unsupported FHIR resource type")
    note = None
    async with pool.acquire() as conn:
        try:
            rows = await conn.fetch(
                """
                SELECT e.run_id, e.target_system, e.canonical_id,
                       e.source_artifact, e.source_location, e.source_line,
                       e.content_sha256, e.dataset_hash, e.transformer_version,
                       e.target_identity, e.confirmed_stage, e.ingested_at,
                       r.status AS run_status
                FROM ingestion_events e
                JOIN pipeline_runs r ON r.run_id = e.run_id
                WHERE e.resource_type = $1 AND e.resource_id = $2
                  AND e.error_message IS NULL AND e.content_sha256 IS NOT NULL
                  AND e.confirmed_stage IN ('load_fhir', 'build_graph')
                ORDER BY e.ingested_at DESC, e.id DESC
                LIMIT 100
                """,
                resource_type,
                resource_id,
            )
        except (asyncpg.UndefinedColumnError, asyncpg.UndefinedTableError):
            rows = []
            note = "Legacy audit schema: run the pipeline to enable resource provenance."
    return {
        "resource_id": f"{resource_type}/{resource_id}",
        "status": "available" if rows else "unavailable",
        "hash_scope": "canonical artifact JSON before server-managed metadata",
        "events": [dict(row) for row in rows],
        "note": note,
    }
