"""Shared FHIR R4 data types used across resource models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class Coding(BaseModel):
    """A reference to a code defined by a terminology system."""

    system: str | None = None
    code: str | None = None
    display: str | None = None


class CodeableConcept(BaseModel):
    """A concept that may be defined by one or more coding systems."""

    coding: list[Coding] = Field(default_factory=list)
    text: str | None = None


class Reference(BaseModel):
    """A reference from one resource to another."""

    reference: str | None = None
    display: str | None = None


class Period(BaseModel):
    """A time period defined by a start and end date/time."""

    start: datetime | None = None
    end: datetime | None = None


class HumanName(BaseModel):
    """A human name with parts."""

    use: str | None = None
    family: str | None = None
    given: list[str] = Field(default_factory=list)
    text: str | None = None


class Address(BaseModel):
    """An address for a person or organization."""

    use: str | None = None
    line: list[str] = Field(default_factory=list)
    city: str | None = None
    state: str | None = None
    postalCode: str | None = None
    country: str | None = None


class ContactPoint(BaseModel):
    """Details for contacting a person or organization."""

    system: str | None = None  # phone, email, etc.
    value: str | None = None
    use: str | None = None


class Quantity(BaseModel):
    """A measured amount with unit."""

    value: float | None = None
    unit: str | None = None
    system: str | None = None
    code: str | None = None


class Identifier(BaseModel):
    """An identifier for a resource."""

    system: str | None = None
    value: str | None = None


class Annotation(BaseModel):
    """A text note with attribution."""

    text: str
    time: datetime | None = None
    authorReference: Reference | None = None


class Dosage(BaseModel):
    """Dosage instructions for a medication."""

    text: str | None = None
    timing: dict[str, Any] | None = None  # Simplified
    route: CodeableConcept | None = None
    doseAndRate: list[dict[str, Any]] | None = None  # Simplified


class BundleEntryRequest(BaseModel):
    """Request part of a Bundle entry (for transaction bundles)."""

    method: str  # GET, POST, PUT, DELETE
    url: str


class BundleEntry(BaseModel):
    """An entry in a FHIR Bundle."""

    fullUrl: str | None = None
    resource: dict[str, Any]  # Serialized resource
    request: BundleEntryRequest | None = None


class Bundle(BaseModel):
    """A FHIR Bundle containing multiple resources."""

    resourceType: str = "Bundle"
    id: str | None = None
    type: str = "transaction"  # transaction, batch, collection, etc.
    entry: list[BundleEntry] = Field(default_factory=list)


# ── Helpers ──


def make_codeable_concept(
    code: str,
    display: str,
    system: str,
    text: str | None = None,
) -> CodeableConcept:
    """Create a CodeableConcept with a single coding."""
    return CodeableConcept(
        coding=[Coding(system=system, code=code, display=display)],
        text=text or display,
    )


def make_reference(resource_type: str, resource_id: str, display: str | None = None) -> Reference:
    """Create a FHIR reference string."""
    return Reference(reference=f"{resource_type}/{resource_id}", display=display)


# Suppress unused import warning — these are re-exported
_ = (date,)
