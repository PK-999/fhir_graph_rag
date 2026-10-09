"""FHIR R4 Encounter resource model."""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

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
    class_: Coding | None = Field(
        default=None, validation_alias="class", serialization_alias="class"
    )  # AMB, IMP, EMER, etc.
    type: list[CodeableConcept] | None = None
    subject: Reference | None = None
    participant: list[dict[str, Any]] | None = None  # simplified
    period: Period | None = None
    serviceProvider: Reference | None = None
    reasonCode: list[CodeableConcept] | None = None

    model_config = ConfigDict(populate_by_name=True)
