"""Hyperlipidemia clinical archetype."""

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
from libs.fhir.models.medication import MedicationRequest
from libs.fhir.models.observation import Observation
from libs.synthetic.archetypes.base import ClinicalArchetype, IdFactoryFn, PatientState

HLD_CODE = "55822004"
HLD_DISPLAY = "Hyperlipidemia"

LDL_CODE = "13457-7"
CHOL_CODE = "2093-3"

ATORVASTATIN_CODE = "2598"
ATORVASTATIN_DISPLAY = "Atorvastatin 40 MG Oral Tablet"


class HyperlipidemiaArchetype(ClinicalArchetype):
    """Hyperlipidemia longitudinal scenario."""

    @property
    def name(self) -> str:
        return "hyperlipidemia"

    def is_compatible(self, gender: str, age: int) -> bool:
        return age >= 25

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

        diagnosed = HLD_CODE in state.active_conditions
        enc_count = state.flags.get("hld_encounters", 0)
        state.flags["hld_encounters"] = enc_count + 1

        # Simulate lipid panel
        if not diagnosed:
            base_ldl = 140 + enc_count * 10
            base_chol = 210 + enc_count * 15
        elif ATORVASTATIN_CODE in state.active_medications:
            base_ldl = 95
            base_chol = 160
        else:
            base_ldl = 160
            base_chol = 240

        ldl = max(50.0, min(300.0, round(rng.gauss(base_ldl, 10), 1)))
        chol = max(100.0, min(400.0, round(rng.gauss(base_chol, 15), 1)))

        obs_id = get_id("Observation")
        resources.append(
            Observation(
                id=obs_id,
                status="final",
                category=[lab_category],
                code=make_codeable_concept(
                    LDL_CODE, "Low density lipoprotein cholesterol", "http://loinc.org"
                ),
                subject=patient_ref,
                encounter=encounter_ref,
                effectiveDateTime=encounter_time,
                valueQuantity=Quantity(
                    value=ldl, unit="mg/dL", system="http://unitsofmeasure.org", code="mg/dL"
                ),
            )
        )

        obs_id = get_id("Observation")
        resources.append(
            Observation(
                id=obs_id,
                status="final",
                category=[lab_category],
                code=make_codeable_concept(CHOL_CODE, "Cholesterol", "http://loinc.org"),
                subject=patient_ref,
                encounter=encounter_ref,
                effectiveDateTime=encounter_time,
                valueQuantity=Quantity(
                    value=chol, unit="mg/dL", system="http://unitsofmeasure.org", code="mg/dL"
                ),
            )
        )

        if not diagnosed and enc_count >= 2:
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
                    code=make_codeable_concept(HLD_CODE, HLD_DISPLAY, "http://snomed.info/sct"),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    onsetDateTime=encounter_time,
                    recordedDate=encounter_time,
                )
            )
            state.active_conditions[HLD_CODE] = encounter_time

            mr_id = get_id("MedicationRequest")
            resources.append(
                MedicationRequest(
                    id=mr_id,
                    status="active",
                    intent="order",
                    medicationCodeableConcept=make_codeable_concept(
                        ATORVASTATIN_CODE,
                        ATORVASTATIN_DISPLAY,
                        "http://www.nlm.nih.gov/research/umls/rxnorm",
                    ),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    authoredOn=encounter_time,
                    requester=practitioner_ref,
                )
            )
            state.active_medications[ATORVASTATIN_CODE] = mr_id

        return resources
