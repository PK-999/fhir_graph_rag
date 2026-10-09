"""FHIR R4 Practitioner and Organization resource models."""

from __future__ import annotations

from typing import Any

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import (
    Address,
    CodeableConcept,
    ContactPoint,
    HumanName,
    Identifier,
)


class Practitioner(FHIRResource):
    """FHIR R4 Practitioner resource."""

    resourceType: str = "Practitioner"
    identifier: list[Identifier] | None = None
    name: list[HumanName] | None = None
    gender: str | None = None
    telecom: list[ContactPoint] | None = None
    qualification: list[dict[str, Any]] | None = None  # simplified

    @property
    def display_name(self) -> str:
        """Return a human-readable name string."""
        if self.name:
            n = self.name[0]
            given = " ".join(n.given) if n.given else ""
            return f"{given} {n.family or ''}".strip()
        return self.id


class Organization(FHIRResource):
    """FHIR R4 Organization resource."""

    resourceType: str = "Organization"
    identifier: list[Identifier] | None = None
    name: str | None = None
    type: list[CodeableConcept] | None = None
    telecom: list[ContactPoint] | None = None
    address: list[Address] | None = None
