"""Hypertension clinical archetype.

Trajectory:
1. Elevated BP readings
2. Hypertension Condition diagnosed
3. Antihypertensive MedicationRequest (Lisinopril)
4. Ongoing BP monitoring with treatment effect
"""

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
    make_reference,
)
from libs.fhir.models.medication import MedicationRequest
from libs.fhir.models.observation import Observation
from libs.synthetic.archetypes.base import ClinicalArchetype, PatientState

HTN_CODE = "38341003"
HTN_DISPLAY = "Hypertension"

SYSTOLIC_CODE = "8480-6"
DIASTOLIC_CODE = "8462-4"

LISINOPRIL_CODE = "29046"
LISINOPRIL_DISPLAY = "Lisinopril 10 MG Oral Tablet"


class HypertensionArchetype(ClinicalArchetype):
    """Hypertension longitudinal scenario."""

    @property
    def name(self) -> str:
        return "hypertension"

    def is_compatible(self, gender: str, age: int) -> bool:
        """Hypertension is rare in children."""
        return age >= 20

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

        diagnosed = HTN_CODE in state.active_conditions
        enc_count = state.flags.get("htn_encounter_count", 0)
        state.flags["htn_encounter_count"] = enc_count + 1

        # Generate BP readings
        if not diagnosed:
            # Pre-diagnosis: gradually rising BP
            base_systolic = 130 + enc_count * 5
            base_diastolic = 82 + enc_count * 3
        elif LISINOPRIL_CODE in state.active_medications:
            # On treatment: controlled BP
            base_systolic = 128
            base_diastolic = 80
        else:
            # Diagnosed but untreated
            base_systolic = 150
            base_diastolic = 95

        systolic = round(rng.gauss(base_systolic, 8), 0)
        systolic = max(90, min(200, systolic))
        diastolic = round(rng.gauss(base_diastolic, 5), 0)
        diastolic = max(55, min(120, diastolic))

        # Systolic BP
        obs_id = get_id("Observation")  # type: ignore[operator]
        resources.append(
            Observation(
                id=obs_id,
                status="final",
                category=[vital_signs_category],
                code=make_codeable_concept(SYSTOLIC_CODE, "Systolic blood pressure", "http://loinc.org"),
                subject=patient_ref,
                encounter=encounter_ref,
                effectiveDateTime=encounter_time,
                valueQuantity=Quantity(
                    value=systolic, unit="mmHg", system="http://unitsofmeasure.org", code="mm[Hg]"
                ),
            )
        )
        state.latest_observations[SYSTOLIC_CODE] = systolic

        # Diastolic BP
        obs_id = get_id("Observation")  # type: ignore[operator]
        resources.append(
            Observation(
                id=obs_id,
                status="final",
                category=[vital_signs_category],
                code=make_codeable_concept(DIASTOLIC_CODE, "Diastolic blood pressure", "http://loinc.org"),
                subject=patient_ref,
                encounter=encounter_ref,
                effectiveDateTime=encounter_time,
                valueQuantity=Quantity(
                    value=diastolic, unit="mmHg", system="http://unitsofmeasure.org", code="mm[Hg]"
                ),
            )
        )
        state.latest_observations[DIASTOLIC_CODE] = diastolic

        # Diagnose after 2 elevated readings
        if not diagnosed and enc_count >= 2:
            condition_id = get_id("Condition")  # type: ignore[operator]
            resources.append(
                Condition(
                    id=condition_id,
                    clinicalStatus=make_codeable_concept(
                        "active", "Active",
                        "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    ),
                    verificationStatus=make_codeable_concept(
                        "confirmed", "Confirmed",
                        "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    ),
                    code=make_codeable_concept(HTN_CODE, HTN_DISPLAY, "http://snomed.info/sct"),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    onsetDateTime=encounter_time,
                    recordedDate=encounter_time,
                )
            )
            state.active_conditions[HTN_CODE] = encounter_time

            # Prescribe Lisinopril
            mr_id = get_id("MedicationRequest")  # type: ignore[operator]
            resources.append(
                MedicationRequest(
                    id=mr_id,
                    status="active",
                    intent="order",
                    medicationCodeableConcept=make_codeable_concept(
                        LISINOPRIL_CODE, LISINOPRIL_DISPLAY,
                        "http://www.nlm.nih.gov/research/umls/rxnorm",
                    ),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    authoredOn=encounter_time,
                    requester=practitioner_ref,
                )
            )
            state.active_medications[LISINOPRIL_CODE] = mr_id

        return resources
