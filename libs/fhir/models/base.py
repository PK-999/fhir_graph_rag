"""Base class for all FHIR R4 resource models."""

from __future__ import annotations

from pydantic import BaseModel


class FHIRResource(BaseModel):
    """Base FHIR R4 resource with common fields."""

    resourceType: str
    id: str

    def to_dict(self) -> dict:
        """Serialize to a FHIR-compatible dict, excluding None values."""
        return self.model_dump(exclude_none=True, by_alias=True, mode="json")
