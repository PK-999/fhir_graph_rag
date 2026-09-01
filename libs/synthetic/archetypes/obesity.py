"""Obesity clinical archetype."""

from __future__ import annotations

import random
from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.condition import Condition
from libs.fhir.models.datatypes import (
    CodeableConcept,
    Coding,
    Quantity,
    Reference,
    make_codeable_concept,
)
from libs.fhir.models.observation import Observation
from libs.synthetic.archetypes.base import ClinicalArchetype, PatientState

OBESITY_CODE = "414916001"
OBESITY_DISPLAY = "Obesity (disorder)"

BMI_CODE = "39156-5"


class ObesityArchetype(ClinicalArchetype):
    """Obesity longitudinal scenario."""

    @property
    def name(self) -> str:
        return "obesity"

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

        vital_category = CodeableConcept(
            coding=[Coding(system="http://terminology.hl7.org/CodeSystem/observation-category", code="vital-signs", display="Vital Signs")]
        )
        patient_ref = Reference(reference=f"Patient/{patient_id}")
        encounter_ref = Reference(reference=f"Encounter/{encounter_id}")

        diagnosed = OBESITY_CODE in state.active_conditions

        # Simulate BMI >= 30
        base_bmi = state.latest_observations.get(BMI_CODE, rng.gauss(32.0, 2.0))
        bmi = max(30.0, min(50.0, round(base_bmi + rng.gauss(0, 0.5), 1)))

        obs_id = get_id("Observation")  # type: ignore[operator]
        resources.append(Observation(
            id=obs_id,
            status="final",
            category=[vital_category],
            code=make_codeable_concept(BMI_CODE, "Body mass index (BMI) [Ratio]", "http://loinc.org"),
            subject=patient_ref, encounter=encounter_ref, effectiveDateTime=encounter_time,
            valueQuantity=Quantity(value=bmi, unit="kg/m2", system="http://unitsofmeasure.org", code="kg/m2")
        ))
        state.latest_observations[BMI_CODE] = bmi

        if not diagnosed:
            condition_id = get_id("Condition")  # type: ignore[operator]
            resources.append(Condition(
                id=condition_id,
                clinicalStatus=make_codeable_concept("active", "Active", "http://terminology.hl7.org/CodeSystem/condition-clinical"),
                verificationStatus=make_codeable_concept("confirmed", "Confirmed", "http://terminology.hl7.org/CodeSystem/condition-ver-status"),
                code=make_codeable_concept(OBESITY_CODE, OBESITY_DISPLAY, "http://snomed.info/sct"),
                subject=patient_ref, encounter=encounter_ref, onsetDateTime=encounter_time, recordedDate=encounter_time
            ))
            state.active_conditions[OBESITY_CODE] = encounter_time

        return resources
