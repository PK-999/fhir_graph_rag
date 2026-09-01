"""Ischemic Heart Disease clinical archetype."""

from __future__ import annotations

import random
from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.condition import Condition
from libs.fhir.models.datatypes import Reference, make_codeable_concept
from libs.synthetic.archetypes.base import ClinicalArchetype, PatientState

IHD_CODE = "414545008"
IHD_DISPLAY = "Ischemic heart disease"


class IHDArchetype(ClinicalArchetype):
    """IHD longitudinal scenario."""

    @property
    def name(self) -> str:
        return "ihd"

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
        id_factory_fn: object,
    ) -> list[FHIRResource]:
        resources: list[FHIRResource] = []
        get_id = id_factory_fn  # type: ignore[assignment]

        patient_ref = Reference(reference=f"Patient/{patient_id}")
        encounter_ref = Reference(reference=f"Encounter/{encounter_id}")

        if IHD_CODE not in state.active_conditions:
            condition_id = get_id("Condition")  # type: ignore[operator]
            resources.append(Condition(
                id=condition_id,
                clinicalStatus=make_codeable_concept("active", "Active", "http://terminology.hl7.org/CodeSystem/condition-clinical"),
                verificationStatus=make_codeable_concept("confirmed", "Confirmed", "http://terminology.hl7.org/CodeSystem/condition-ver-status"),
                code=make_codeable_concept(IHD_CODE, IHD_DISPLAY, "http://snomed.info/sct"),
                subject=patient_ref, encounter=encounter_ref, onsetDateTime=encounter_time, recordedDate=encounter_time
            ))
            state.active_conditions[IHD_CODE] = encounter_time

        return resources
