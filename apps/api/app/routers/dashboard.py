"""Dashboard API router."""

from typing import Any

from apps.api.app.dependencies import db
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/dashboard")


async def get_neo4j_session():
    if not db.neo4j_driver:
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    async with db.neo4j_driver.session() as session:
        yield session


@router.get("/summary")
async def get_dashboard_summary(session=Depends(get_neo4j_session)) -> dict[str, Any]:
    """Get high-level summary counts from Neo4j."""
    query = """
    CALL { MATCH (p:Patient) RETURN count(p) AS patients }
    CALL { MATCH (e:Encounter) RETURN count(e) AS encounters }
    CALL { MATCH (c:Condition) RETURN count(c) AS conditions }
    CALL { MATCH (o:Observation) RETURN count(o) AS observations }
    CALL { MATCH (m:MedicationRequest) RETURN count(m) AS medications }
    CALL { MATCH (pr:Procedure) RETURN count(pr) AS procedures }
    CALL { MATCH (n) RETURN count(n) AS graph_nodes }
    CALL { MATCH ()-[r]->() RETURN count(r) AS graph_edges }
    RETURN patients, encounters, conditions, observations, medications, procedures, graph_nodes, graph_edges
    """

    result = await session.run(query)
    record = await result.single()

    if not record:
        return {}

    return {
        "patients": record["patients"],
        "encounters": record["encounters"],
        "conditions": record["conditions"],
        "observations": record["observations"],
        "medications": record["medications"],
        "procedures": record["procedures"],
        "graph_nodes": record["graph_nodes"],
        "graph_edges": record["graph_edges"],
    }
