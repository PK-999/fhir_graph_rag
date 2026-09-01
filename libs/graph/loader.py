"""Neo4j graph loader for batched idempotent ingestion."""

import logging
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase
from neo4j.exceptions import ClientError

from libs.graph.schema import GraphEdge, GraphNode

logger = logging.getLogger(__name__)


class Neo4jLoader:
    """Client for loading GraphNodes and GraphEdges into Neo4j."""

    def __init__(self, uri: str = "bolt://localhost:7687", auth: tuple[str, str] = ("neo4j", "password")) -> None:
        self.driver: AsyncDriver = AsyncGraphDatabase.driver(uri, auth=auth)

    async def close(self) -> None:
        """Close the database driver."""
        await self.driver.close()

    async def verify_connectivity(self) -> None:
        """Check connection to the Neo4j database."""
        await self.driver.verify_connectivity()

    async def run_query(self, query: str, parameters: dict[str, Any] | None = None) -> Any:
        """Run a single query."""
        async with self.driver.session() as session:
            result = await session.run(query, parameters)
            return await result.data()

    async def load_nodes(self, nodes: list[GraphNode]) -> int:
        """Load nodes in a batch using UNWIND and MERGE."""
        if not nodes:
            return 0

        # Group nodes by their primary label to allow MERGE on label
        grouped: dict[str, list[dict]] = {}
        for node in nodes:
            # First label is treated as the primary structural label
            primary_label = node.labels[0]
            if primary_label not in grouped:
                grouped[primary_label] = []

            # Neo4j cannot merge dynamically on variable labels,
            # so we merge on primary, then SET remaining labels and props.
            grouped[primary_label].append({
                "id": node.id,
                "labels": node.labels,
                "props": node.properties
            })

        total_loaded = 0
        async with self.driver.session() as session:
            for label, batch in grouped.items():
                query = f"""
                UNWIND $batch AS row
                MERGE (n:{label} {{id: row.id}})
                SET n += row.props
                WITH n, row
                CALL apoc.create.addLabels(n, row.labels) YIELD node
                RETURN count(node) as c
                """

                # Without APOC, we'd have to construct dynamic queries or ignore secondary labels.
                # A fallback if APOC is not available:
                fallback_query = f"""
                UNWIND $batch AS row
                MERGE (n:{label} {{id: row.id}})
                SET n += row.props
                RETURN count(n) as c
                """

                try:
                    result = await session.run(query, batch=batch)
                except ClientError as e:
                    if "apoc" in str(e).lower() or "procedure not found" in str(e).lower():
                        logger.warning("APOC not installed. Falling back to primary labels only.")
                        result = await session.run(fallback_query, batch=batch)
                    else:
                        raise e

                record = await result.single()
                if record:
                    total_loaded += record["c"]

        return total_loaded

    async def load_edges(self, edges: list[GraphEdge]) -> int:
        """Load edges in a batch using UNWIND and MERGE."""
        if not edges:
            return 0

        # Group by edge type
        grouped: dict[str, list[dict]] = {}
        for edge in edges:
            if edge.type not in grouped:
                grouped[edge.type] = []

            grouped[edge.type].append({
                "source": edge.source_id,
                "target": edge.target_id,
                "props": edge.properties
            })

        total_loaded = 0
        async with self.driver.session() as session:
            for edge_type, batch in grouped.items():
                # We do not specify labels for source/target because we have globally unique IDs across types
                # (e.g. "Patient/p-001" and "Concept/123").
                query = f"""
                UNWIND $batch AS row
                MATCH (s {{id: row.source}})
                MATCH (t {{id: row.target}})
                MERGE (s)-[r:{edge_type}]->(t)
                SET r += row.props
                RETURN count(r) as c
                """
                result = await session.run(query, batch=batch)
                record = await result.single()
                if record:
                    total_loaded += record["c"]

        return total_loaded
