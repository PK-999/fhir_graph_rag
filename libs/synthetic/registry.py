"""In-memory resource and reference registry.

Tracks all created resource IDs and all FHIR references as edges.
Used for referential integrity validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from libs.fhir.references import extract_references


@dataclass
class ReferenceEdge:
    """A reference from one resource to another."""

    source: str  # e.g. "Observation/p-000001-o-0014"
    field_name: str  # e.g. "subject"
    target: str  # e.g. "Patient/p-000001"


class ResourceRegistry:
    """Tracks all FHIR resources and their references for integrity checks."""

    def __init__(self) -> None:
        self._resources: dict[str, set[str]] = {}  # type -> set of full IDs
        self._references: list[ReferenceEdge] = []
        self._all_ids: set[str] = set()

    def register(self, resource_type: str, resource_id: str) -> str:
        """Register a resource and return its full qualified ID (Type/id)."""
        full_id = f"{resource_type}/{resource_id}"
        if full_id in self._all_ids:
            raise ValueError(f"Duplicate resource ID: {full_id}")
        self._resources.setdefault(resource_type, set()).add(full_id)
        self._all_ids.add(full_id)
        return full_id

    def add_reference(self, source: str, field_name: str, target: str) -> None:
        """Record a reference edge from source to target."""
        self._references.append(ReferenceEdge(source=source, field_name=field_name, target=target))

    def register_resource(
        self,
        resource_type: str,
        resource_id: str,
        payload: dict[str, Any],
    ) -> str:
        """Register a resource and every nested FHIR reference in its payload."""
        full_id = self.register(resource_type, resource_id)
        for target in extract_references(payload):
            self.add_reference(full_id, "reference", target)
        return full_id

    def get_dangling_references(self) -> list[ReferenceEdge]:
        """Return references that point to unregistered resources."""
        return [ref for ref in self._references if ref.target not in self._all_ids]

    def get_duplicate_ids(self) -> list[str]:
        """Return any duplicate IDs (should always be empty if register() is used)."""
        # This is inherently empty because register() raises on duplicates,
        # but kept for external validation use cases.
        return []

    def resource_count(self, resource_type: str) -> int:
        """Return count of resources of a given type."""
        return len(self._resources.get(resource_type, set()))

    def total_count(self) -> int:
        """Return total count of all resources."""
        return len(self._all_ids)

    @property
    def all_ids(self) -> set[str]:
        """Return all registered resource IDs."""
        return self._all_ids.copy()

    @property
    def resource_counts(self) -> dict[str, int]:
        """Return counts per resource type."""
        return {k: len(v) for k, v in self._resources.items()}

    @property
    def reference_count(self) -> int:
        """Total number of tracked references."""
        return len(self._references)

    def validate(self) -> None:
        """Raise if any referential integrity violations exist."""
        dangling = self.get_dangling_references()
        if dangling:
            details = "\n".join(f"  {r.source}.{r.field_name} -> {r.target}" for r in dangling[:20])
            raise ValueError(
                f"Referential integrity violation: {len(dangling)} dangling references:\n{details}"
            )
