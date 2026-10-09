"""Encounter generator — creates encounters and linked resources for each patient."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, timedelta

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import (
    CodeableConcept,
    Coding,
    Period,
    make_reference,
)
from libs.fhir.models.encounter import Encounter
from libs.fhir.models.practitioner import Organization, Practitioner
from libs.synthetic.archetypes.base import ClinicalArchetype, PatientState
from libs.synthetic.id_factory import IdFactory
from libs.synthetic.registry import ResourceRegistry

# Encounter class codes (FHIR)
ENCOUNTER_CLASSES = [
    ("AMB", "ambulatory", 0.50),
    ("WELLNESS", "wellness", 0.15),
    ("EMER", "emergency", 0.10),
    ("IMP", "inpatient encounter", 0.15),
    ("ACUTE", "inpatient acute", 0.05),
    ("URGNT", "urgent", 0.05),
]


def generate_encounters(
    patient_id: str,
    patient_birth_date: date,
    patient_gender: str,
    patient_age: int,
    archetypes: list[ClinicalArchetype],
    practitioners: list[Practitioner],
    organizations: list[Organization],
    id_factory: IdFactory,
    registry: ResourceRegistry,
    rng: random.Random,
    config_encounters_min: int,
    config_encounters_max: int,
    config_history_years: int,
    patient_seq: int,
    reference_date: date | None = None,
) -> list[FHIRResource]:
    """Generate all encounters and linked resources for a single patient.

    Returns a flat list of all FHIR resources (encounters + clinical resources).
    """
    if reference_date is None:
        reference_date = date(2026, 8, 30)

    all_resources: list[FHIRResource] = []

    # Determine encounter count
    encounter_count = rng.randint(config_encounters_min, config_encounters_max)

    # Generate encounter timestamps spread across history period
    history_start = reference_date - timedelta(days=config_history_years * 365)
    # Ensure no encounter before birth
    earliest = max(history_start, patient_birth_date + timedelta(days=30))
    total_days = (reference_date - earliest).days
    if total_days <= 0:
        total_days = 365  # fallback

    # Generate sorted encounter dates
    encounter_dates = sorted(
        earliest + timedelta(days=rng.randint(0, total_days)) for _ in range(encounter_count)
    )

    # Patient state persists across encounters
    state = PatientState()

    for _enc_idx, enc_date in enumerate(encounter_dates, start=1):
        # Pick encounter class
        classes, weights = zip(*[(c[:2], c[2]) for c in ENCOUNTER_CLASSES], strict=True)
        enc_class_code, enc_class_display = rng.choices(classes, weights=weights, k=1)[0]

        # Encounter timing
        enc_start = datetime(
            enc_date.year,
            enc_date.month,
            enc_date.day,
            rng.randint(7, 17),
            rng.randint(0, 59),
            tzinfo=UTC,
        )
        # Duration depends on class
        if enc_class_code in ("IMP", "ACUTE"):
            duration_hours = rng.randint(24, 72)
        elif enc_class_code == "EMER":
            duration_hours = rng.randint(2, 8)
        else:
            duration_hours = rng.randint(0, 2)
        enc_end = enc_start + timedelta(hours=duration_hours)

        # Pick practitioner and organization
        practitioner = rng.choice(practitioners)
        organization = rng.choice(organizations)

        # Generate encounter ID
        enc_id = id_factory.resource_id(patient_seq, "Encounter")

        # Create encounter
        encounter = Encounter(
            id=enc_id,
            status="finished",
            class_=Coding(
                system="http://terminology.hl7.org/CodeSystem/v3-ActCode",
                code=enc_class_code,
                display=enc_class_display,
            ),
            type=[
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://snomed.info/sct",
                            code="185347001",
                            display="Encounter for problem",
                        )
                    ]
                )
            ],
            subject=make_reference("Patient", patient_id),
            participant=[
                {
                    "individual": make_reference(
                        "Practitioner", practitioner.id, practitioner.display_name
                    ).model_dump(exclude_none=True)
                }
            ],
            period=Period(start=enc_start, end=enc_end),
            serviceProvider=make_reference("Organization", organization.id, organization.name),
        )
        all_resources.append(encounter)

        # Register the encounter and all serialized references generically.
        registry.register_resource("Encounter", enc_id, encounter.to_dict())

        # Apply archetypes to generate clinical resources
        practitioner_ref = make_reference(
            "Practitioner", practitioner.id, practitioner.display_name
        )

        def _make_id(resource_type: str) -> str:
            return id_factory.resource_id(patient_seq, resource_type)

        for archetype in archetypes:
            if not archetype.is_compatible(patient_gender, patient_age):
                continue

            resources = archetype.apply(
                patient_id=patient_id,
                encounter_id=enc_id,
                encounter_time=enc_start,
                state=state,
                rng=rng,
                practitioner_ref=practitioner_ref,
                id_factory_fn=_make_id,
            )

            for resource in resources:
                registry.register_resource(
                    resource.resourceType,
                    resource.id,
                    resource.to_dict(),
                )
                all_resources.append(resource)

    return all_resources
