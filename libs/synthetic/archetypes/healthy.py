"""Generally healthy / preventive care archetype.

Generates routine vitals and wellness observations.
"""

from __future__ import annotations

import random
from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import (
    CodeableConcept,
    Coding,
    Quantity,
    Reference,
    make_codeable_concept,
    make_reference,
)
from libs.fhir.models.observation import Observation
from libs.synthetic.archetypes.base import ClinicalArchetype, PatientState


class HealthyArchetype(ClinicalArchetype):
    """Generates routine vitals for generally healthy patients."""

    @property
    def name(self) -> str:
        return "healthy"

    def apply(
        self,
        patient_id: str,
        encounter_id: str,
        encounter_time: datetime,
        state: PatientState,
        rng: random.Random,
        practitioner_ref: Reference,
        id_factory_fn: object,
    ) -> list[FHIRResource]:
        resources: list[FHIRResource] = []
        get_id = id_factory_fn  # type: ignore[assignment]

        patient_ref = make_reference("Patient", patient_id)
        encounter_ref = make_reference("Encounter", encounter_id)

        vital_signs_category = CodeableConcept(
            coding=[
                Coding(
                    system="http://terminology.hl7.org/CodeSystem/observation-category",
                    code="vital-signs",
                    display="Vital Signs",
                )
            ]
        )

        # Body weight (kg)
        weight = round(rng.gauss(75, 12), 1)
        weight = max(40.0, min(150.0, weight))
        obs_id = get_id("Observation")  # type: ignore[operator]
        resources.append(
            Observation(
                id=obs_id,
                status="final",
                category=[vital_signs_category],
                code=make_codeable_concept("29463-7", "Body weight", "http://loinc.org"),
                subject=patient_ref,
                encounter=encounter_ref,
                effectiveDateTime=encounter_time,
                valueQuantity=Quantity(value=weight, unit="kg", system="http://unitsofmeasure.org", code="kg"),
            )
        )
        state.latest_observations["29463-7"] = weight

        # Heart rate
        hr = rng.randint(60, 95)
        obs_id = get_id("Observation")  # type: ignore[operator]
        resources.append(
            Observation(
                id=obs_id,
                status="final",
                category=[vital_signs_category],
                code=make_codeable_concept("8867-4", "Heart rate", "http://loinc.org"),
                subject=patient_ref,
                encounter=encounter_ref,
                effectiveDateTime=encounter_time,
                valueQuantity=Quantity(value=float(hr), unit="/min", system="http://unitsofmeasure.org", code="/min"),
            )
        )
        state.latest_observations["8867-4"] = float(hr)

        # Temperature
        temp = round(rng.gauss(36.8, 0.3), 1)
        temp = max(36.0, min(37.5, temp))
        obs_id = get_id("Observation")  # type: ignore[operator]
        resources.append(
            Observation(
                id=obs_id,
                status="final",
                category=[vital_signs_category],
                code=make_codeable_concept("8310-5", "Body temperature", "http://loinc.org"),
                subject=patient_ref,
                encounter=encounter_ref,
                effectiveDateTime=encounter_time,
                valueQuantity=Quantity(value=temp, unit="Cel", system="http://unitsofmeasure.org", code="Cel"),
            )
        )
        state.latest_observations["8310-5"] = temp

        return resources
