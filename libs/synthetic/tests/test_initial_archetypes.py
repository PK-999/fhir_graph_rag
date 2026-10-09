"""Deterministic contracts for the three Milestone 1 clinical scenarios."""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.condition import Condition
from libs.fhir.models.datatypes import make_reference
from libs.fhir.models.medication import MedicationRequest
from libs.fhir.models.observation import Observation
from libs.synthetic.archetypes.base import PatientState
from libs.synthetic.archetypes.diabetes import (
    DIABETES_CODE,
    HBA1C_CODE,
    METFORMIN_CODE,
    DiabetesArchetype,
)
from libs.synthetic.archetypes.healthy import HealthyArchetype
from libs.synthetic.archetypes.hypertension import (
    DIASTOLIC_CODE,
    HTN_CODE,
    LISINOPRIL_CODE,
    SYSTOLIC_CODE,
    HypertensionArchetype,
)


def _id_factory() -> Callable[[str], str]:
    counters: dict[str, int] = {}

    def make_id(resource_type: str) -> str:
        counters[resource_type] = counters.get(resource_type, 0) + 1
        return f"{resource_type.lower()}-{counters[resource_type]}"

    return make_id


def _code(resource: FHIRResource) -> str | None:
    concept = resource.code if isinstance(resource, (Condition, Observation)) else None
    if concept and concept.coding:
        code = concept.coding[0].code
        return code if isinstance(code, str) else None
    return None


def _medication_code(resource: MedicationRequest) -> str | None:
    concept = resource.medicationCodeableConcept
    if concept and concept.coding:
        return concept.coding[0].code
    return None


def _quantity_value(resource: Observation) -> float:
    assert resource.valueQuantity is not None
    assert resource.valueQuantity.value is not None
    return resource.valueQuantity.value


def test_healthy_scenario_emits_coded_vitals_with_plausible_values() -> None:
    resources = HealthyArchetype().apply(
        patient_id="p-000001",
        encounter_id="e-0001",
        encounter_time=datetime(2026, 1, 1, tzinfo=UTC),
        state=PatientState(),
        rng=random.Random(11),
        practitioner_ref=make_reference("Practitioner", "pract-0001"),
        id_factory_fn=_id_factory(),
    )

    observation_resources = [
        resource for resource in resources if isinstance(resource, Observation)
    ]
    observations = {
        resource.code.coding[0].code: resource
        for resource in observation_resources
        if resource.code and resource.code.coding and resource.code.coding[0].code
    }
    assert set(observations) == {"29463-7", "8867-4", "8310-5"}
    assert 40 <= _quantity_value(observations["29463-7"]) <= 150
    assert 60 <= _quantity_value(observations["8867-4"]) <= 95
    assert 36 <= _quantity_value(observations["8310-5"]) <= 37.5
    assert all(
        resource.subject and resource.subject.reference == "Patient/p-000001"
        for resource in observation_resources
    )
    assert all(
        resource.encounter and resource.encounter.reference == "Encounter/e-0001"
        for resource in observation_resources
    )


def test_diabetes_scenario_observes_before_diagnosis_and_metformin() -> None:
    archetype = DiabetesArchetype()
    state = PatientState()
    make_id = _id_factory()
    start = datetime(2025, 1, 1, tzinfo=UTC)
    visits: list[list[FHIRResource]] = []

    for index in range(5):
        visits.append(
            archetype.apply(
                patient_id="p-000001",
                encounter_id=f"e-{index + 1}",
                encounter_time=start + timedelta(days=90 * index),
                state=state,
                rng=random.Random(100 + index),
                practitioner_ref=make_reference("Practitioner", "pract-0001"),
                id_factory_fn=make_id,
            )
        )

    assert all(
        not any(isinstance(resource, (Condition, MedicationRequest)) for resource in visit)
        for visit in visits[:3]
    )
    assert all(
        {_code(resource) for resource in visit} == {"2345-7", HBA1C_CODE} for visit in visits[:3]
    )
    diagnosis = next(resource for resource in visits[3] if isinstance(resource, Condition))
    medication = next(resource for resource in visits[3] if isinstance(resource, MedicationRequest))
    assert _code(diagnosis) == DIABETES_CODE
    assert _medication_code(medication) == METFORMIN_CODE
    assert diagnosis.onsetDateTime == medication.authoredOn == start + timedelta(days=270)
    assert DIABETES_CODE in state.active_conditions
    assert METFORMIN_CODE in state.active_medications
    assert {_code(resource) for resource in visits[4]} == {"2345-7", HBA1C_CODE}


def test_hypertension_scenario_requires_repeated_readings_before_treatment() -> None:
    archetype = HypertensionArchetype()
    state = PatientState()
    make_id = _id_factory()
    start = datetime(2025, 1, 1, tzinfo=UTC)
    visits: list[list[FHIRResource]] = []

    for index in range(4):
        visits.append(
            archetype.apply(
                patient_id="p-000001",
                encounter_id=f"e-{index + 1}",
                encounter_time=start + timedelta(days=60 * index),
                state=state,
                rng=random.Random(200 + index),
                practitioner_ref=make_reference("Practitioner", "pract-0001"),
                id_factory_fn=make_id,
            )
        )

    assert all(
        not any(isinstance(resource, (Condition, MedicationRequest)) for resource in visit)
        for visit in visits[:2]
    )
    assert all(
        {_code(resource) for resource in visit} == {SYSTOLIC_CODE, DIASTOLIC_CODE}
        for visit in visits[:2]
    )
    diagnosis = next(resource for resource in visits[2] if isinstance(resource, Condition))
    medication = next(resource for resource in visits[2] if isinstance(resource, MedicationRequest))
    assert _code(diagnosis) == HTN_CODE
    assert _medication_code(medication) == LISINOPRIL_CODE
    assert diagnosis.onsetDateTime == medication.authoredOn == start + timedelta(days=120)
    assert HTN_CODE in state.active_conditions
    assert LISINOPRIL_CODE in state.active_medications
    assert {_code(resource) for resource in visits[3]} == {SYSTOLIC_CODE, DIASTOLIC_CODE}
    assert all(isinstance(resource, Observation) for resource in visits[3])
