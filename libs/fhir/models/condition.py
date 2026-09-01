"""FHIR R4 Condition resource model."""

from __future__ import annotations

from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import CodeableConcept, Reference


class Condition(FHIRResource):
    """FHIR R4 Condition resource."""

    resourceType: str = "Condition"
    clinicalStatus: CodeableConcept | None = None
    verificationStatus: CodeableConcept | None = None
    category: list[CodeableConcept] | None = None
    code: CodeableConcept | None = None
    subject: Reference | None = None
    encounter: Reference | None = None
    onsetDateTime: datetime | None = None
    recordedDate: datetime | None = None
