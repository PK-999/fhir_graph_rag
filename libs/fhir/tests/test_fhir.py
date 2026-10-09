"""Tests for FHIR reference extraction and models."""

from __future__ import annotations

from datetime import date

from libs.fhir.models.datatypes import HumanName
from libs.fhir.models.encounter import Encounter
from libs.fhir.models.patient import Patient
from libs.fhir.references import extract_references, validate_references


class TestReferenceExtraction:
    """Test FHIR reference extraction."""

    def test_extract_subject_reference(self) -> None:
        resource = {
            "resourceType": "Observation",
            "id": "o-001",
            "subject": {"reference": "Patient/p-001"},
        }
        refs = list(extract_references(resource))
        assert "Patient/p-001" in refs

    def test_extract_nested_references(self) -> None:
        resource = {
            "resourceType": "Encounter",
            "id": "e-001",
            "subject": {"reference": "Patient/p-001"},
            "participant": [{"individual": {"reference": "Practitioner/pract-0001"}}],
            "serviceProvider": {"reference": "Organization/org-0001"},
        }
        refs = list(extract_references(resource))
        assert len(refs) == 3
        assert "Patient/p-001" in refs
        assert "Practitioner/pract-0001" in refs
        assert "Organization/org-0001" in refs

    def test_validate_references_all_resolved(self) -> None:
        resource = {"subject": {"reference": "Patient/p-001"}}
        known = {"Patient/p-001"}
        assert validate_references(resource, known) == []

    def test_validate_references_unresolved(self) -> None:
        resource = {"subject": {"reference": "Patient/p-999"}}
        known = {"Patient/p-001"}
        unresolved = validate_references(resource, known)
        assert "Patient/p-999" in unresolved


class TestPatientModel:
    """Test FHIR Patient model."""

    def test_to_dict(self) -> None:
        p = Patient(
            id="p-000001",
            gender="male",
            birthDate=date(1980, 5, 15),
            name=[HumanName(use="official", family="Smith", given=["John"])],
        )
        d = p.to_dict()
        assert d["resourceType"] == "Patient"
        assert d["id"] == "p-000001"
        assert d["gender"] == "male"

    def test_display_name(self) -> None:
        p = Patient(
            id="p-000001",
            name=[HumanName(family="Smith", given=["John"])],
        )
        assert p.display_name == "John Smith"


def test_encounter_class_survives_fhir_round_trip() -> None:
    payload = {
        "resourceType": "Encounter",
        "id": "e-001",
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
    }
    encounter = Encounter.model_validate(payload)
    assert encounter.class_ is not None
    assert encounter.to_dict()["class"] == payload["class"]
    assert "class_" not in encounter.to_dict()


def test_resource_serialization_omits_empty_repeating_fields_without_mutating_model() -> None:
    from libs.fhir.models.datatypes import Address
    from libs.fhir.models.practitioner import Organization

    organization = Organization(id="org1", address=[Address(city="Example City")])

    payload = organization.to_dict()

    assert payload["address"] == [{"city": "Example City"}]
    assert organization.address is not None
    assert organization.address[0].line == []
