"""Graph canonical models for Neo4j ingestion."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """A node in the knowledge graph."""
    id: str
    labels: list[str]
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """A directed edge in the knowledge graph."""
    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
