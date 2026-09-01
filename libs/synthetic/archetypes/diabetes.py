"""Type 2 Diabetes clinical archetype.

Implements the diabetes trajectory:
1. Risk/metabolic observations
2. Elevated glucose/HbA1c
3. Diabetes Condition diagnosed
4. Subsequent monitoring
5. MedicationRequest (Metformin)
6. Trending observations
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

# SNOMED code for Type 2 Diabetes
DIABETES_CODE = "44054006"
DIABETES_DISPLAY = "Type 2 diabetes mellitus"

# LOINC codes
GLUCOSE_CODE = "2345-7"
HBA1C_CODE = "4548-4"

# RxNorm for Metformin
METFORMIN_CODE = "6809"
METFORMIN_DISPLAY = "Metformin 500 MG Oral Tablet"


class DiabetesArchetype(ClinicalArchetype):
    """Type 2 Diabetes longitudinal scenario."""

    @property
    def name(self) -> str:
        return "diabetes"

    def is_compatible(self, gender: str, age: int) -> bool:
        """T2D is rare in children; prevalence rises with age."""
        return age >= 18

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

        lab_category = CodeableConcept(
            coding=[
                Coding(
                    system="http://terminology.hl7.org/CodeSystem/observation-category",
                    code="laboratory",
                    display="Laboratory",
                )
            ]
        )

        diagnosed = DIABETES_CODE in state.active_conditions
        encounter_count = state.flags.get("diabetes_encounter_count", 0)
        state.flags["diabetes_encounter_count"] = encounter_count + 1

        # Phase 1-2: Pre-diagnosis — elevated glucose/HbA1c
        if not diagnosed and encounter_count < 3:
            # Glucose trending up
            base_glucose = 100 + encounter_count * 15
            glucose = round(rng.gauss(base_glucose, 10), 1)
            glucose = max(80, min(250, glucose))

            obs_id = get_id("Observation")  # type: ignore[operator]
            resources.append(
                Observation(
                    id=obs_id,
                    status="final",
                    category=[lab_category],
                    code=make_codeable_concept(GLUCOSE_CODE, "Glucose", "http://loinc.org"),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    effectiveDateTime=encounter_time,
                    valueQuantity=Quantity(
                        value=glucose, unit="mg/dL", system="http://unitsofmeasure.org", code="mg/dL"
                    ),
                )
            )
            state.latest_observations[GLUCOSE_CODE] = glucose

            # HbA1c trending up
            base_hba1c = 5.5 + encounter_count * 0.8
            hba1c = round(rng.gauss(base_hba1c, 0.3), 1)
            hba1c = max(4.5, min(14.0, hba1c))

            obs_id = get_id("Observation")  # type: ignore[operator]
            resources.append(
                Observation(
                    id=obs_id,
                    status="final",
                    category=[lab_category],
                    code=make_codeable_concept(HBA1C_CODE, "Hemoglobin A1c", "http://loinc.org"),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    effectiveDateTime=encounter_time,
                    valueQuantity=Quantity(
                        value=hba1c, unit="%", system="http://unitsofmeasure.org", code="%"
                    ),
                )
            )
            state.latest_observations[HBA1C_CODE] = hba1c

        # Phase 3: Diagnosis
        elif not diagnosed and encounter_count >= 3:
            # Diagnose diabetes
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
                    code=make_codeable_concept(
                        DIABETES_CODE, DIABETES_DISPLAY, "http://snomed.info/sct"
                    ),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    onsetDateTime=encounter_time,
                    recordedDate=encounter_time,
                )
            )
            state.active_conditions[DIABETES_CODE] = encounter_time

            # Start Metformin
            mr_id = get_id("MedicationRequest")  # type: ignore[operator]
            resources.append(
                MedicationRequest(
                    id=mr_id,
                    status="active",
                    intent="order",
                    medicationCodeableConcept=make_codeable_concept(
                        METFORMIN_CODE, METFORMIN_DISPLAY, "http://www.nlm.nih.gov/research/umls/rxnorm"
                    ),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    authoredOn=encounter_time,
                    requester=practitioner_ref,
                )
            )
            state.active_medications[METFORMIN_CODE] = mr_id

            # Elevated HbA1c at diagnosis
            hba1c = round(rng.gauss(8.5, 0.8), 1)
            hba1c = max(7.0, min(13.0, hba1c))
            obs_id = get_id("Observation")  # type: ignore[operator]
            resources.append(
                Observation(
                    id=obs_id,
                    status="final",
                    category=[lab_category],
                    code=make_codeable_concept(HBA1C_CODE, "Hemoglobin A1c", "http://loinc.org"),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    effectiveDateTime=encounter_time,
                    valueQuantity=Quantity(
                        value=hba1c, unit="%", system="http://unitsofmeasure.org", code="%"
                    ),
                )
            )
            state.latest_observations[HBA1C_CODE] = hba1c

        # Phase 4-6: Post-diagnosis monitoring
        else:
            # Monitoring HbA1c — may trend down with treatment
            prev_hba1c = state.latest_observations.get(HBA1C_CODE, 8.5)
            delta = rng.gauss(-0.2, 0.4)  # slight improvement trend
            hba1c = round(prev_hba1c + delta, 1)
            hba1c = max(5.0, min(13.0, hba1c))

            obs_id = get_id("Observation")  # type: ignore[operator]
            resources.append(
                Observation(
                    id=obs_id,
                    status="final",
                    category=[lab_category],
                    code=make_codeable_concept(HBA1C_CODE, "Hemoglobin A1c", "http://loinc.org"),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    effectiveDateTime=encounter_time,
                    valueQuantity=Quantity(
                        value=hba1c, unit="%", system="http://unitsofmeasure.org", code="%"
                    ),
                )
            )
            state.latest_observations[HBA1C_CODE] = hba1c

            # Glucose monitoring
            glucose = round(rng.gauss(130 + (hba1c - 7) * 15, 15), 1)
            glucose = max(70, min(300, glucose))
            obs_id = get_id("Observation")  # type: ignore[operator]
            resources.append(
                Observation(
                    id=obs_id,
                    status="final",
                    category=[lab_category],
                    code=make_codeable_concept(GLUCOSE_CODE, "Glucose", "http://loinc.org"),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    effectiveDateTime=encounter_time,
                    valueQuantity=Quantity(
                        value=glucose, unit="mg/dL", system="http://unitsofmeasure.org", code="mg/dL"
                    ),
                )
            )
            state.latest_observations[GLUCOSE_CODE] = glucose

        return resources
