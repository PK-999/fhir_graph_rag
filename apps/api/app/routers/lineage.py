"""Lineage API router."""

from typing import Any

from apps.api.app.dependencies import db
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/lineage")


async def get_pg_pool():
    if not db.pg_pool:
        raise HTTPException(status_code=503, detail="PostgreSQL not connected")
    return db.pg_pool


@router.get("")
async def get_lineage_mappings(pool=Depends(get_pg_pool)) -> dict[str, Any]:
    """Get all lineage mappings from PostgreSQL."""
    query = """
    SELECT business_domain, business_entity, business_attribute, fhir_resource_type as fhir_resource, fhir_element, description
    FROM lineage_mappings
    """
    async with pool.acquire() as conn:
        mappings = await conn.fetch(query)

    return {"mappings": [dict(m) for m in mappings]}
