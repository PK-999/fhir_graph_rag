"""FHIR R4 Observation resource model."""

from __future__ import annotations

from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import CodeableConcept, Quantity, Reference


class Observation(FHIRResource):
    """FHIR R4 Observation resource."""

    resourceType: str = "Observation"
    status: str = "final"  # registered, preliminary, final, amended
    category: list[CodeableConcept] | None = None
    code: CodeableConcept | None = None
    subject: Reference | None = None
    encounter: Reference | None = None
    effectiveDateTime: datetime | None = None
    valueQuantity: Quantity | None = None
    interpretation: list[CodeableConcept] | None = None
    referenceRange: list[dict] | None = None  # simplified
