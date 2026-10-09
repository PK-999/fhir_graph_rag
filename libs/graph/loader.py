"""Neo4j graph loader for batched idempotent ingestion."""

import re
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from libs.graph.schema import GraphEdge, GraphNode

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _validate_identifier(value: str) -> None:
    """Validate identifiers embedded in Cypher rather than passed as parameters."""
    if _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"Invalid Cypher label or relationship type: {value!r}")


class Neo4jLoader:
    """Client for loading GraphNodes and GraphEdges into Neo4j."""

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        auth: tuple[str, str] = ("neo4j", "password"),
        batch_size: int = 500,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        self.batch_size = batch_size
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

        # Each label combination gets a static query, so secondary labels need no APOC.
        grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
        for node in nodes:
            if not node.labels:
                raise ValueError(f"Node {node.id!r} must have at least one label")
            for label in node.labels:
                _validate_identifier(label)
            labels = tuple(dict.fromkeys(node.labels))
            grouped.setdefault(labels, []).append({"id": node.id, "props": node.properties})

        total_loaded = 0
        async with self.driver.session() as session:
            for labels, batch in grouped.items():
                secondary_labels = ":".join(labels[1:])
                set_labels = f"SET n:{secondary_labels}" if secondary_labels else ""
                query = f"""
                UNWIND $batch AS row
                MERGE (n:{labels[0]} {{id: row.id}})
                SET n += row.props
                {set_labels}
                RETURN count(n) as c
                """
                for offset in range(0, len(batch), self.batch_size):
                    chunk = batch[offset : offset + self.batch_size]
                    result = await session.run(query, batch=chunk)
                    record = await result.single()
                    if record is None or record["c"] != len(chunk):
                        raise ValueError("Not every graph input was loaded")
                    total_loaded += record["c"]

        return total_loaded

    async def load_edges(self, edges: list[GraphEdge]) -> int:
        """Load edges in a batch using UNWIND and MERGE."""
        if not edges:
            return 0

        # Static endpoint labels allow Neo4j to use the per-resource ID indexes.
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for edge in edges:
            _validate_identifier(edge.type)
            labels = [
                identifier.split("/", 1)[0] for identifier in (edge.source_id, edge.target_id)
            ]
            for label in labels:
                _validate_identifier(label)
            key = (edge.type, labels[0], labels[1])
            grouped.setdefault(key, []).append(
                {"source": edge.source_id, "target": edge.target_id, "props": edge.properties}
            )

        total_loaded = 0
        async with self.driver.session() as session:
            for (edge_type, source_label, target_label), batch in grouped.items():
                query = f"""
                UNWIND $batch AS row
                MATCH (s:{source_label} {{id: row.source}})
                MATCH (t:{target_label} {{id: row.target}})
                MERGE (s)-[r:{edge_type}]->(t)
                SET r += row.props
                RETURN count(r) as c
                """
                for offset in range(0, len(batch), self.batch_size):
                    chunk = batch[offset : offset + self.batch_size]
                    result = await session.run(query, batch=chunk)
                    record = await result.single()
                    if record is None or record["c"] != len(chunk):
                        raise ValueError("Not every graph input was loaded")
                    total_loaded += record["c"]

        return total_loaded
