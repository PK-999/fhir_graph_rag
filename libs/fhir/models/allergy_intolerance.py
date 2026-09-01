"""FHIR R4 AllergyIntolerance resource model."""

from __future__ import annotations

from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import CodeableConcept, Reference


class AllergyIntolerance(FHIRResource):
    """FHIR R4 AllergyIntolerance resource."""

    resourceType: str = "AllergyIntolerance"
    clinicalStatus: CodeableConcept | None = None
    verificationStatus: CodeableConcept | None = None
    type: str | None = None  # allergy, intolerance
    category: list[str] | None = None  # food, medication, environment, biologic
    code: CodeableConcept | None = None
    patient: Reference | None = None
    encounter: Reference | None = None
    onsetDateTime: datetime | None = None
    recordedDate: datetime | None = None
