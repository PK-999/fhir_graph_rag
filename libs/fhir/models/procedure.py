"""FHIR R4 Procedure, DiagnosticReport, and ServiceRequest resource models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import CodeableConcept, Reference


class Procedure(FHIRResource):
    """FHIR R4 Procedure resource."""

    resourceType: str = "Procedure"
    status: str = "completed"  # preparation, in-progress, completed, etc.
    code: CodeableConcept | None = None
    subject: Reference | None = None
    encounter: Reference | None = None
    performedDateTime: datetime | None = None
    performer: list[dict[str, Any]] | None = None  # simplified
    reasonCode: list[CodeableConcept] | None = None


class DiagnosticReport(FHIRResource):
    """FHIR R4 DiagnosticReport resource."""

    resourceType: str = "DiagnosticReport"
    status: str = "final"  # registered, partial, preliminary, final
    category: list[CodeableConcept] | None = None
    code: CodeableConcept | None = None
    subject: Reference | None = None
    encounter: Reference | None = None
    effectiveDateTime: datetime | None = None
    issued: datetime | None = None
    result: list[Reference] | None = None
    conclusion: str | None = None


class ServiceRequest(FHIRResource):
    """FHIR R4 ServiceRequest resource."""

    resourceType: str = "ServiceRequest"
    status: str = "completed"  # draft, active, completed, etc.
    intent: str = "order"
    code: CodeableConcept | None = None
    subject: Reference | None = None
    encounter: Reference | None = None
    authoredOn: datetime | None = None
    requester: Reference | None = None
