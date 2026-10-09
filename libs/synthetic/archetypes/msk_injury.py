"""Musculoskeletal (MSK) Injury archetype."""

from __future__ import annotations

import random
from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.condition import Condition
from libs.fhir.models.datatypes import Reference, make_codeable_concept
from libs.fhir.models.medication import MedicationRequest
from libs.fhir.models.procedure import DiagnosticReport
from libs.synthetic.archetypes.base import ClinicalArchetype, IdFactoryFn, PatientState

SPRAIN_CODE = "44465007"
SPRAIN_DISPLAY = "Sprain of ankle"
XRAY_CODE = "168731009"
XRAY_DISPLAY = "Standard radiography of ankle"
IBUPROFEN_CODE = "5640"
IBUPROFEN_DISPLAY = "Ibuprofen 400 MG Oral Tablet"


class MskInjuryArchetype(ClinicalArchetype):
    """MSK Injury scenario (sprained ankle)."""

    @property
    def name(self) -> str:
        return "msk_injury"

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

        # Only apply once per patient history
        if "msk_injury" in state.flags:
            return resources

        state.flags["msk_injury"] = True
        get_id = id_factory_fn

        patient_ref = Reference(reference=f"Patient/{patient_id}")
        encounter_ref = Reference(reference=f"Encounter/{encounter_id}")

        # Condition
        condition_id = get_id("Condition")
        resources.append(
            Condition(
                id=condition_id,
                clinicalStatus=make_codeable_concept(
                    "resolved",
                    "Resolved",
                    "http://terminology.hl7.org/CodeSystem/condition-clinical",
                ),
                verificationStatus=make_codeable_concept(
                    "confirmed",
                    "Confirmed",
                    "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                ),
                code=make_codeable_concept(SPRAIN_CODE, SPRAIN_DISPLAY, "http://snomed.info/sct"),
                subject=patient_ref,
                encounter=encounter_ref,
                onsetDateTime=encounter_time,
                recordedDate=encounter_time,
            )
        )

        # X-Ray DiagnosticReport
        report_id = get_id("DiagnosticReport")
        resources.append(
            DiagnosticReport(
                id=report_id,
                status="final",
                code=make_codeable_concept(XRAY_CODE, XRAY_DISPLAY, "http://snomed.info/sct"),
                subject=patient_ref,
                encounter=encounter_ref,
                effectiveDateTime=encounter_time,
                issued=encounter_time,
                conclusion="No acute fracture.",
            )
        )

        # Medication (Ibuprofen)
        mr_id = get_id("MedicationRequest")
        resources.append(
            MedicationRequest(
                id=mr_id,
                status="completed",
                intent="order",
                medicationCodeableConcept=make_codeable_concept(
                    IBUPROFEN_CODE, IBUPROFEN_DISPLAY, "http://www.nlm.nih.gov/research/umls/rxnorm"
                ),
                subject=patient_ref,
                encounter=encounter_ref,
                authoredOn=encounter_time,
                requester=practitioner_ref,
            )
        )

        return resources
