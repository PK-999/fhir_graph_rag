"""FHIR R4 Medication and MedicationRequest resource models."""

from __future__ import annotations

from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import CodeableConcept, Dosage, Reference


class Medication(FHIRResource):
    """FHIR R4 Medication resource."""

    resourceType: str = "Medication"
    code: CodeableConcept | None = None
    status: str | None = "active"


class MedicationRequest(FHIRResource):
    """FHIR R4 MedicationRequest resource."""

    resourceType: str = "MedicationRequest"
    status: str = "active"  # active, completed, cancelled, etc.
    intent: str = "order"  # proposal, plan, order, etc.
    medicationCodeableConcept: CodeableConcept | None = None
    medicationReference: Reference | None = None
    subject: Reference | None = None
    encounter: Reference | None = None
    authoredOn: datetime | None = None
    requester: Reference | None = None
    dosageInstruction: list[Dosage] | None = None
