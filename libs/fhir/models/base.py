"""Base class for all FHIR R4 resource models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class FHIRResource(BaseModel):
    """Base FHIR R4 resource with common fields."""

    resourceType: str
    id: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a FHIR-compatible dict, excluding None values."""
        return _omit_empty_arrays(self.model_dump(exclude_none=True, by_alias=True, mode="json"))


def _omit_empty_arrays(payload: dict[str, Any]) -> dict[str, Any]:
    """Omit absent repeating fields in a fresh serialization, never in source data."""
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, list):
            if value:
                result[key] = [
                    _omit_empty_arrays(item) if isinstance(item, dict) else item for item in value
                ]
        elif isinstance(value, dict):
            result[key] = _omit_empty_arrays(value)
        else:
            result[key] = value
    return result
