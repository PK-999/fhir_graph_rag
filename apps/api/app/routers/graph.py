"""Graph API router."""

from typing import Any

from apps.api.app.dependencies import db
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/graph")

# ── Safety constants ──
MAX_NODES = 200
MAX_EDGES = 500
MAX_DEPTH = 3
QUERY_TIMEOUT_SECONDS = 30


async def get_neo4j_session():
    if not db.neo4j_driver:
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    async with db.neo4j_driver.session() as session:
        yield session


@router.get("/neighbors/{node_id:path}")
async def get_neighbors(
    node_id: str,
    depth: int = Query(default=1, ge=1, le=MAX_DEPTH),
    session=Depends(get_neo4j_session)
) -> dict[str, Any]:
    """Get graph neighbors up to a certain depth.

    Result set is bounded to MAX_NODES nodes and MAX_EDGES edges to
    prevent resource exhaustion on high-degree neighborhoods.
    """
    # The query limits expanded paths to prevent combinatorial explosion,
    # then truncates collected nodes/edges to hard ceilings.
    query = f"""
    MATCH path = (n {{id: $id}})-[*1..{depth}]-(m)
    WITH path LIMIT 1000
    WITH reduce(ns = [], p IN collect(path) | ns + nodes(p)) AS allNodes
    UNWIND allNodes AS node
    WITH collect(DISTINCT node)[..{MAX_NODES}] AS nodes
    MATCH (a)-[r]->(b)
    WHERE a IN nodes AND b IN nodes
    WITH nodes, collect(DISTINCT r)[..{MAX_EDGES}] AS edges
    RETURN nodes, edges
    """

    result = await session.run(
        query,
        {"id": node_id},
        timeout=QUERY_TIMEOUT_SECONDS,
    )
    record = await result.single()

    if not record:
        return {"nodes": [], "edges": [], "truncated": False}

    def _format_node(n):
        return {"id": n["id"], "labels": list(n.labels), "properties": dict(n)}

    def _format_edge(r):
        return {
            "type": r.type,
            "source": r.start_node["id"],
            "target": r.end_node["id"],
            "properties": dict(r)
        }

    nodes = [_format_node(n) for n in record["nodes"]]
    edges = [_format_edge(r) for r in record["edges"]]

    return {
        "nodes": nodes,
        "edges": edges,
        "truncated": len(nodes) >= MAX_NODES or len(edges) >= MAX_EDGES,
    }


@router.get("/explore/{node_id:path}/expand")
async def expand_node(
    node_id: str,
    relationship: str = Query(..., description="The relationship type to expand"),
    target_label: str = Query(..., description="The target node label to expand"),
    limit: int = Query(default=25, le=100),
    session=Depends(get_neo4j_session),
) -> dict[str, Any]:
    """Fetch specific neighbors based on relationship and label for additive expansion."""
    # Ensure relationship and label are alphanumeric to prevent injection since they are dynamic
    if not relationship.replace("_", "").isalnum() or not target_label.isalnum():
        raise HTTPException(status_code=400, detail="Invalid relationship or label")

    query = f"""
    MATCH (n {{id: $id}})-[r:{relationship}]-(m:{target_label})
    RETURN n, m, r
    LIMIT $limit
    """

    result = await session.run(query, {"id": node_id, "limit": limit})
    
    nodes = []
    edges = []
    
    def _format_node(n):
        return {"id": n["id"], "labels": list(n.labels), "properties": dict(n)}

    def _format_edge(r):
        return {
            "type": r.type,
            "source": r.start_node["id"],
            "target": r.end_node["id"],
            "properties": dict(r)
        }

    async for record in result:
        m = record["m"]
        r = record["r"]
        nodes.append(_format_node(m))
        edges.append(_format_edge(r))

    return {"nodes": nodes, "edges": edges}


@router.get("/explore/{node_id:path}")
async def explore_node(
    node_id: str,
    session=Depends(get_neo4j_session),
) -> dict[str, Any]:
    """Return categorized expansion options for a node.

    Instead of dumping all neighbors, this returns counts per label
    and relationship type so the UI can offer guided expansion choices.
    """
    query = """
    MATCH (n {id: $id})
    OPTIONAL MATCH (n)-[r]-(m)
    WITH n,
         labels(n) AS source_labels,
         type(r) AS rel_type,
         labels(m) AS neighbor_labels,
         m
    WITH n, source_labels,
         rel_type,
         head(neighbor_labels) AS neighbor_label,
         count(DISTINCT m) AS cnt
    RETURN source_labels,
           collect({
             relationship: rel_type,
             neighbor_type: neighbor_label,
             count: cnt
           }) AS categories
    """

    result = await session.run(query, {"id": node_id}, timeout=QUERY_TIMEOUT_SECONDS)
    record = await result.single()

    if not record:
        return {"node_id": node_id, "labels": [], "categories": []}

    categories = [
        c for c in record["categories"]
        if c["relationship"] is not None
    ]

    return {
        "node_id": node_id,
        "labels": record["source_labels"],
        "categories": categories,
    }

