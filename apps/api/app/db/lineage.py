"""Metadata and Lineage seeding logic."""

from apps.api.app.db.models import LineageMapping
from sqlalchemy.orm import Session

SEED_MAPPINGS = [
    {
        "business_domain": "Clinical",
        "business_entity": "Lab Results",
        "business_attribute": "HbA1c Value",
        "fhir_resource": "Observation",
        "fhir_element": "valueQuantity",
        "description": "Hemoglobin A1c test result indicating average blood sugar levels."
    },
    {
        "business_domain": "Clinical",
        "business_entity": "Diagnoses",
        "business_attribute": "Condition Code",
        "fhir_resource": "Condition",
        "fhir_element": "code",
        "description": "SNOMED CT code identifying the diagnosed condition."
    },
    {
        "business_domain": "Clinical",
        "business_entity": "Medications",
        "business_attribute": "Prescription",
        "fhir_resource": "MedicationRequest",
        "fhir_element": "medicationCodeableConcept",
        "description": "RxNorm code for the prescribed medication."
    },
    {
        "business_domain": "Demographics",
        "business_entity": "Patient Profile",
        "business_attribute": "Date of Birth",
        "fhir_resource": "Patient",
        "fhir_element": "birthDate",
        "description": "Patient's date of birth."
    },
    {
        "business_domain": "Clinical",
        "business_entity": "Encounters",
        "business_attribute": "Encounter Date",
        "fhir_resource": "Encounter",
        "fhir_element": "period.start",
        "description": "Start timestamp of the clinical encounter."
    }
]

def seed_lineage_data(session: Session) -> None:
    """Seed the lineage_mappings table with predefined mappings."""
    # Check if already seeded
    if session.query(LineageMapping).count() > 0:
        return

    for mapping in SEED_MAPPINGS:
        lm = LineageMapping(**mapping)
        session.add(lm)

    session.commit()
