"""Asthma clinical archetype."""

from __future__ import annotations

import random
from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.condition import Condition
from libs.fhir.models.datatypes import Reference, make_codeable_concept
from libs.fhir.models.medication import MedicationRequest
from libs.synthetic.archetypes.base import ClinicalArchetype, IdFactoryFn, PatientState

ASTHMA_CODE = "195967001"
ASTHMA_DISPLAY = "Asthma"
ALBUTEROL_CODE = "2123111"
ALBUTEROL_DISPLAY = "Albuterol 90 MCG/ACTUAT Inhaler"


class AsthmaArchetype(ClinicalArchetype):
    """Asthma longitudinal scenario."""

    @property
    def name(self) -> str:
        return "asthma"

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

        patient_ref = Reference(reference=f"Patient/{patient_id}")
        encounter_ref = Reference(reference=f"Encounter/{encounter_id}")

        diagnosed = ASTHMA_CODE in state.active_conditions

        if not diagnosed:
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
                    code=make_codeable_concept(
                        ASTHMA_CODE, ASTHMA_DISPLAY, "http://snomed.info/sct"
                    ),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    onsetDateTime=encounter_time,
                    recordedDate=encounter_time,
                )
            )
            state.active_conditions[ASTHMA_CODE] = encounter_time

            mr_id = get_id("MedicationRequest")
            resources.append(
                MedicationRequest(
                    id=mr_id,
                    status="active",
                    intent="order",
                    medicationCodeableConcept=make_codeable_concept(
                        ALBUTEROL_CODE,
                        ALBUTEROL_DISPLAY,
                        "http://www.nlm.nih.gov/research/umls/rxnorm",
                    ),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    authoredOn=encounter_time,
                    requester=practitioner_ref,
                )
            )
            state.active_medications[ALBUTEROL_CODE] = mr_id

        return resources
