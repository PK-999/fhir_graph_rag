"""FHIR R4 Patient resource model."""

from __future__ import annotations

from datetime import date
from typing import Any

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import (
    Address,
    CodeableConcept,
    ContactPoint,
    HumanName,
    Identifier,
)


class Patient(FHIRResource):
    """FHIR R4 Patient resource."""

    resourceType: str = "Patient"
    identifier: list[Identifier] | None = None
    name: list[HumanName] | None = None
    gender: str | None = None  # male, female, other, unknown
    birthDate: date | None = None
    address: list[Address] | None = None
    telecom: list[ContactPoint] | None = None
    maritalStatus: CodeableConcept | None = None
    communication: list[dict[str, Any]] | None = None  # simplified

    @property
    def display_name(self) -> str:
        """Return a human-readable name string."""
        if self.name:
            n = self.name[0]
            given = " ".join(n.given) if n.given else ""
            return f"{given} {n.family or ''}".strip()
        return self.id
