"""FHIR R4 Encounter resource model."""

from __future__ import annotations

from pydantic import ConfigDict

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import (
    CodeableConcept,
    Coding,
    Identifier,
    Period,
    Reference,
)


class EncounterParticipant(FHIRResource):
    """A participant in an encounter (simplified)."""

    resourceType: str = "EncounterParticipant"
    individual: Reference | None = None
    type: list[CodeableConcept] | None = None


class Encounter(FHIRResource):
    """FHIR R4 Encounter resource."""

    resourceType: str = "Encounter"
    identifier: list[Identifier] | None = None
    status: str = "finished"  # planned, arrived, triaged, in-progress, finished, etc.
    class_: Coding | None = None  # AMB, IMP, EMER, etc.
    type: list[CodeableConcept] | None = None
    subject: Reference | None = None
    participant: list[dict] | None = None  # simplified
    period: Period | None = None
    serviceProvider: Reference | None = None
    reasonCode: list[CodeableConcept] | None = None

    model_config = ConfigDict(populate_by_name=True)

    def to_dict(self) -> dict:
        """Override to rename class_ → class in output."""
        d = super().to_dict()
        if "class_" in d:
            d["class"] = d.pop("class_")
        return d
