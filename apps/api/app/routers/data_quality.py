"""Data Quality API router."""

import json
from typing import Any

from apps.api.app.dependencies import get_pg_pool
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/data-quality")


@router.get("/summary")
async def get_dq_summary(pool: Any = Depends(get_pg_pool)) -> dict[str, Any]:
    """Get the latest data quality summary."""
    query = """
    SELECT pr.run_id as id, pr.status, pr.started_at as start_time, pr.completed_at as end_time, pr.config_snapshot, pr.error_message
    FROM pipeline_runs pr
    ORDER BY pr.started_at DESC
    LIMIT 1
    """
    async with pool.acquire() as conn:
        latest_run = await conn.fetchrow(query)
        if not latest_run:
            return {"latest_run": None, "results": []}

        results_query = """
        SELECT rule_name, CASE WHEN passed THEN 'pass' ELSE 'fail' END as status,
               CASE WHEN passed THEN 100 ELSE 0 END as pass_rate, details
        FROM data_quality_results
        WHERE run_id = $1
        """
        results = await conn.fetch(results_query, latest_run["id"])

    run = dict(latest_run)
    if isinstance(run.get("config_snapshot"), str):
        run["config_snapshot"] = json.loads(run["config_snapshot"])
    quality = [dict(r) for r in results]
    for item in quality:
        if isinstance(item.get("details"), str):
            item["details"] = json.loads(item["details"])
    return {"latest_run": run, "results": quality}
