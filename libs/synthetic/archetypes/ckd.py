"""Chronic Kidney Disease clinical archetype."""

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
from libs.synthetic.archetypes.base import ClinicalArchetype, IdFactoryFn, PatientState

CKD_CODE = "709044004"
CKD_DISPLAY = "Chronic kidney disease"
EGFR_CODE = "33914-3"


class CKDArchetype(ClinicalArchetype):
    """CKD longitudinal scenario."""

    @property
    def name(self) -> str:
        return "ckd"

    def is_compatible(self, gender: str, age: int) -> bool:
        return age >= 50

    def apply(
        self,
        patient_id: str,
        encounter_id: str,
        encounter_time: datetime,
        state: PatientState,
        rng: random.Random,
        practitioner_ref: Reference,
        id_factory_fn: IdFactoryFn,
    ) -> list[FHIRResource]:
        resources: list[FHIRResource] = []
        get_id = id_factory_fn

        lab_category = CodeableConcept(
            coding=[
                Coding(
                    system="http://terminology.hl7.org/CodeSystem/observation-category",
                    code="laboratory",
                    display="Laboratory",
                )
            ]
        )
        patient_ref = Reference(reference=f"Patient/{patient_id}")
        encounter_ref = Reference(reference=f"Encounter/{encounter_id}")

        diagnosed = CKD_CODE in state.active_conditions

        # Simulate eGFR decreasing over time
        base_egfr = state.latest_observations.get(EGFR_CODE, rng.gauss(65.0, 5.0))
        egfr = max(15.0, min(100.0, round(base_egfr - rng.gauss(1.0, 1.0), 1)))

        obs_id = get_id("Observation")
        resources.append(
            Observation(
                id=obs_id,
                status="final",
                category=[lab_category],
                code=make_codeable_concept(EGFR_CODE, "Estimated GFR", "http://loinc.org"),
                subject=patient_ref,
                encounter=encounter_ref,
                effectiveDateTime=encounter_time,
                valueQuantity=Quantity(
                    value=egfr,
                    unit="mL/min/1.73m2",
                    system="http://unitsofmeasure.org",
                    code="mL/min/{1.73_m2}",
                ),
            )
        )
        state.latest_observations[EGFR_CODE] = egfr

        if not diagnosed and egfr < 60:
            condition_id = get_id("Condition")
            resources.append(
                Condition(
                    id=condition_id,
                    clinicalStatus=make_codeable_concept(
                        "active",
                        "Active",
                        "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    ),
                    verificationStatus=make_codeable_concept(
                        "confirmed",
                        "Confirmed",
                        "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    ),
                    code=make_codeable_concept(CKD_CODE, CKD_DISPLAY, "http://snomed.info/sct"),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    onsetDateTime=encounter_time,
                    recordedDate=encounter_time,
                )
            )
            state.active_conditions[CKD_CODE] = encounter_time

        return resources
