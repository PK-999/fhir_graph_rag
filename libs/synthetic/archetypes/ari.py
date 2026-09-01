"""Acute Respiratory Infection archetype."""

from __future__ import annotations

import random
from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.condition import Condition
from libs.fhir.models.datatypes import Reference, make_codeable_concept
from libs.synthetic.archetypes.base import ClinicalArchetype, PatientState

ARI_CODE = "195662009"
ARI_DISPLAY = "Acute respiratory infection"


class ARIArchetype(ClinicalArchetype):
    """Acute Respiratory Infection scenario."""

    @property
    def name(self) -> str:
        return "ari"

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

        if "ari" in state.flags:
            return resources

        state.flags["ari"] = True
        get_id = id_factory_fn  # type: ignore[assignment]

        patient_ref = Reference(reference=f"Patient/{patient_id}")
        encounter_ref = Reference(reference=f"Encounter/{encounter_id}")

        # Condition
        condition_id = get_id("Condition")  # type: ignore[operator]
        resources.append(Condition(
            id=condition_id,
            clinicalStatus=make_codeable_concept("resolved", "Resolved", "http://terminology.hl7.org/CodeSystem/condition-clinical"),
            verificationStatus=make_codeable_concept("confirmed", "Confirmed", "http://terminology.hl7.org/CodeSystem/condition-ver-status"),
            code=make_codeable_concept(ARI_CODE, ARI_DISPLAY, "http://snomed.info/sct"),
            subject=patient_ref, encounter=encounter_ref, onsetDateTime=encounter_time, recordedDate=encounter_time
        ))

        return resources
