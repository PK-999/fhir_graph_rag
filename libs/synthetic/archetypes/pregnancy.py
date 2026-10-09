"""Pregnancy clinical archetype."""

from __future__ import annotations

import random
from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.condition import Condition
from libs.fhir.models.datatypes import Reference, make_codeable_concept
from libs.fhir.models.procedure import DiagnosticReport, Procedure
from libs.synthetic.archetypes.base import ClinicalArchetype, IdFactoryFn, PatientState

PREGNANCY_CODE = "77386006"
PREGNANCY_DISPLAY = "Patient currently pregnant"
ULTRASOUND_CODE = "16310003"
ULTRASOUND_DISPLAY = "Diagnostic ultrasonography (procedure)"


class PregnancyArchetype(ClinicalArchetype):
    """Pregnancy longitudinal scenario."""

    @property
    def name(self) -> str:
        return "pregnancy"

    def is_compatible(self, gender: str, age: int) -> bool:
        return gender == "female" and 18 <= age <= 45

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

        diagnosed = PREGNANCY_CODE in state.active_conditions

        if not diagnosed:
            # Diagnose pregnancy
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
                        PREGNANCY_CODE, PREGNANCY_DISPLAY, "http://snomed.info/sct"
                    ),
                    subject=patient_ref,
                    encounter=encounter_ref,
                    onsetDateTime=encounter_time,
                    recordedDate=encounter_time,
                )
            )
            state.active_conditions[PREGNANCY_CODE] = encounter_time
        else:
            # Check if this encounter is a follow up where they get an ultrasound
            had_ultrasound = state.flags.get("pregnancy_ultrasound", False)
            if not had_ultrasound and rng.random() > 0.5:
                # Issue ultrasound Procedure and DiagnosticReport
                proc_id = get_id("Procedure")
                resources.append(
                    Procedure(
                        id=proc_id,
                        status="completed",
                        code=make_codeable_concept(
                            ULTRASOUND_CODE, ULTRASOUND_DISPLAY, "http://snomed.info/sct"
                        ),
                        subject=patient_ref,
                        encounter=encounter_ref,
                        performedDateTime=encounter_time,
                    )
                )

                report_id = get_id("DiagnosticReport")
                resources.append(
                    DiagnosticReport(
                        id=report_id,
                        status="final",
                        code=make_codeable_concept(
                            ULTRASOUND_CODE, ULTRASOUND_DISPLAY, "http://snomed.info/sct"
                        ),
                        subject=patient_ref,
                        encounter=encounter_ref,
                        effectiveDateTime=encounter_time,
                        issued=encounter_time,
                        conclusion="Normal fetal development.",
                    )
                )
                state.flags["pregnancy_ultrasound"] = True

        return resources
