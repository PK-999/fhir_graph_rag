"""Data Quality API router."""

from typing import Any

from apps.api.app.dependencies import db
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/data-quality")


async def get_pg_pool():
    if not db.pg_pool:
        raise HTTPException(status_code=503, detail="PostgreSQL not connected")
    return db.pg_pool


@router.get("/summary")
async def get_dq_summary(pool=Depends(get_pg_pool)) -> dict[str, Any]:
    """Get the latest data quality summary."""
    query = """
    SELECT pr.run_id as id, pr.status, pr.started_at as start_time, pr.completed_at as end_time
    FROM pipeline_runs pr
    ORDER BY pr.started_at DESC
    LIMIT 1
    """
    async with pool.acquire() as conn:
        latest_run = await conn.fetchrow(query)
        if not latest_run:
            return {"latest_run": None, "results": []}

        results_query = """
        SELECT rule_name, CASE WHEN passed THEN 'Pass' ELSE 'Fail' END as status, 100 as pass_rate, details
        FROM data_quality_results
        WHERE run_id = $1
        """
        results = await conn.fetch(results_query, latest_run["id"])

    return {
        "latest_run": dict(latest_run),
        "results": [dict(r) for r in results]
    }
