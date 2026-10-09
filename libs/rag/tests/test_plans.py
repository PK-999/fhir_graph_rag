"""Question plans are strict and never carry executable model-written queries."""

import pytest
from pydantic import ValidationError

from libs.rag.evidence import build_response
from libs.rag.plans import QueryPlan, parse_question
from libs.rag.queries import compile_plan


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "patient_list", "cypher": "DELETE n"},
        {"intent": "patient_list", "limit": 101},
        {"intent": "condition_cohort"},
        {"intent": "latest_lab_medication", "lab_code": "4548-4"},
        {"intent": "patient_history", "patient_id": "Patient/x/DELETE"},
        {"intent": "patient_list", "condition_code": "44054006"},
    ],
)
def test_plan_rejects_extra_or_incomplete_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        QueryPlan.model_validate(payload)


def test_demo_question_resolves_known_terminology() -> None:
    plan = parse_question("Find patients whose latest HbA1c is above 8% with active Metformin")
    assert plan is not None
    assert plan.intent == "latest_lab_medication"
    assert (plan.lab_code, plan.medication_code, plan.threshold, plan.unit) == (
        "4548-4",
        "6809",
        8,
        "%",
    )
    listing = parse_question("List five patients")
    assert listing is not None and listing.limit == 5
    cohort = parse_question("Find patients with type 2 diabetes")
    assert cohort is not None and cohort.condition_code == "44054006"


@pytest.mark.parametrize(
    "question",
    [
        "What treatment should these patients take?",
        "Delete all patients",
        "List five patients with cancer",
        "Find patients with type 2 diabetes who are over 65",
        "Find patients whose latest HbA1c is above 8 with Metformin and kidney disease",
    ],
)
def test_partial_question_interpretation_abstains(question: str) -> None:
    assert parse_question(question) is None


def test_out_of_range_threshold_abstains_instead_of_crashing() -> None:
    assert (
        parse_question("Find patients whose latest HbA1c is above 999999 with active Metformin")
        is None
    )


def test_additional_condition_filter_returns_condition_evidence_fields() -> None:
    plan = QueryPlan(
        intent="latest_lab_medication",
        lab_code="4548-4",
        medication_code="6809",
        threshold=8,
        unit="%",
        condition_code="44054006",
    )
    query, parameters = compile_plan(plan)
    assert "c.id AS condition_id" in query
    assert "c.code_coding_0_code = $condition_code" in query
    assert parameters["condition_code"] == "44054006"


def test_latest_lab_is_selected_before_value_filter_and_uses_parameters() -> None:
    plan = QueryPlan(
        intent="latest_lab_medication",
        lab_code="4548-4",
        medication_code="6809",
        threshold=8,
        unit="%",
    )
    query, params = compile_plan(plan)
    assert query.index("head(collect(o))") < query.index("o.value_quantity_value > $threshold")
    assert "datetime(o.effective_date_time).epochSeconds DESC" in query
    assert "datetime(o.effective_date_time).nanosecond DESC, o.id DESC" in query
    assert "(o:Observation)-[:SUBJECT]->(p:Patient)" in query
    assert params["threshold"] == 8
    assert "4548-4" not in query


def test_condition_code_is_data_not_query_text() -> None:
    code = "x' MATCH (n) DELETE n"
    query, params = compile_plan(QueryPlan(intent="condition_cohort", condition_code=code))
    assert code not in query
    assert params["condition_code"] == code


def test_answer_has_exact_clinical_source_fields_and_no_total_claim() -> None:
    plan = QueryPlan(
        intent="latest_lab_medication",
        lab_code="4548-4",
        medication_code="6809",
        threshold=8,
        unit="%",
    )
    rows = [
        {
            "patient_id": "Patient/p-1",
            "name": "Test Patient",
            "given": "Test",
            "family": "Patient",
            "observation_id": "Observation/o-2",
            "value": 9.2,
            "unit": "%",
            "observed_at": "2026-01-01T00:00:00Z",
            "lab_code": "4548-4",
            "medication_id": "MedicationRequest/m-1",
            "medication_code": "6809",
            "medication_status": "active",
        }
    ]
    response = build_response(plan, rows, "demo", "query", {})
    assert response["status"] == "answered"
    assert "limited" in response["answer"].lower()
    obs = next(item for item in response["evidence"] if item["type"] == "Observation")
    assert obs["facts"]["Observation.valueQuantity.value"] == 9.2
    assert obs["source_url"] == "/resources/Observation/o-2"
    assert obs["patient_id"] == "Patient/p-1"
    assert len(response["evidence"]) == 3


def test_zero_matches_does_not_claim_patient_has_no_disease() -> None:
    response = build_response(
        QueryPlan(intent="condition_cohort", condition_code="44054006"), [], "demo", "query", {}
    )
    assert response["result_count"] == 0
    assert response["evidence"] == []
    assert "no matching" in response["answer"].lower()


def test_history_cites_encounter_and_prescription_dates_as_recorded_fields() -> None:
    response = build_response(
        QueryPlan(intent="patient_history", patient_id="Patient/p"),
        [
            {
                "patient_id": "Patient/p",
                "resource_id": "Encounter/e",
                "resource_type": "Encounter",
                "status": "finished",
                "event_at": "2025-02-01T12:00:00Z",
                "event_field": "Encounter.period.start",
            },
            {
                "patient_id": "Patient/p",
                "resource_id": "MedicationRequest/m",
                "resource_type": "MedicationRequest",
                "status": "active",
                "medication_code": "6809",
                "event_at": "2025-01-01T12:00:00Z",
                "event_field": "MedicationRequest.authoredOn",
            },
        ],
        "demo",
        "query",
        {},
    )
    citations = {item["id"]: item for item in response["evidence"]}
    assert citations["Encounter/e"]["facts"]["Encounter.period.start"] == "2025-02-01T12:00:00Z"
    assert (
        citations["MedicationRequest/m"]["facts"]["MedicationRequest.authoredOn"]
        == "2025-01-01T12:00:00Z"
    )
    assert "recorded" in response["answer"].lower()


@pytest.mark.parametrize(
    "question,intent,fields",
    [
        ("Can you list five patients?", "patient_list", {"limit": 5}),
        (
            "Which patients have type 2 diabetes?",
            "condition_cohort",
            {"condition_code": "44054006"},
        ),
        ("Who has hypertension?", "condition_cohort", {"condition_code": "38341003"}),
        (
            "Which patients have active Metformin prescriptions?",
            "medication_cohort",
            {"medication_code": "6809"},
        ),
        (
            "Find patients on active Metformin with type 2 diabetes",
            "medication_cohort",
            {"medication_code": "6809", "condition_code": "44054006"},
        ),
        ("Show lab history for Patient/P-1", "patient_lab_history", {"patient_id": "Patient/P-1"}),
        (
            "What are the HbA1c results for Patient/P-1?",
            "patient_lab_history",
            {"patient_id": "Patient/P-1", "lab_code": "4548-4"},
        ),
        (
            "Can you show the history for Patient/P-1?",
            "patient_history",
            {"patient_id": "Patient/P-1"},
        ),
        (
            "Which patients have latest HbA1c above 8% and active Metformin?",
            "latest_lab_medication",
            {"threshold": 8.0, "medication_code": "6809"},
        ),
        (
            "List patients diagnosed with hypertension",
            "condition_cohort",
            {"condition_code": "38341003"},
        ),
        (
            "Which patients have a diagnosis of type 2 diabetes?",
            "condition_cohort",
            {"condition_code": "44054006"},
        ),
        (
            "List patients with active prescriptions for Metformin",
            "medication_cohort",
            {"medication_code": "6809"},
        ),
        (
            "What is the lab history for Patient/P-1?",
            "patient_lab_history",
            {"patient_id": "Patient/P-1"},
        ),
        ("What is the history for Patient/P-1?", "patient_history", {"patient_id": "Patient/P-1"}),
        (
            "Find patients with latest HbA1c greater than 8% who have active Metformin prescriptions",
            "latest_lab_medication",
            {"threshold": 8.0, "medication_code": "6809"},
        ),
        (
            "Which patients have latest HbA1c above 8% and active Metformin with type 2 diabetes?",
            "latest_lab_medication",
            {"threshold": 8.0, "condition_code": "44054006"},
        ),
    ],
)
def test_complete_question_paraphrases_preserve_every_supported_filter(
    question: str, intent: str, fields: dict[str, object]
) -> None:
    plan = parse_question(question)
    assert plan is not None
    assert plan.intent == intent
    assert all(getattr(plan, key) == value for key, value in fields.items())


@pytest.mark.parametrize(
    "question",
    [
        "Which patients have active Metformin prescriptions and kidney disease?",
        "Which patients have active Metformin prescriptions who are over 65?",
        "Find patients on active Metformin without type 2 diabetes",
        "Show HbA1c history for Patient/p since January 2025",
        "Show lab history for Patient/p above 8%",
        "Which patients have latest HbA1c above 8% and active Metformin and cancer?",
    ],
)
def test_new_question_patterns_never_drop_unsupported_filters(question: str) -> None:
    assert parse_question(question) is None


def test_medication_cohort_is_unique_per_patient_and_cites_recorded_status_and_date() -> None:
    plan = QueryPlan(intent="medication_cohort", medication_code="6809", condition_code="44054006")
    query, parameters = compile_plan(plan, offset=20)
    assert "head(collect(m))" in query
    assert "m.status = 'active'" in query
    assert "m.authored_on AS authored_on" in query
    assert "c.id AS condition_id" in query
    assert parameters["offset"] == 20 and parameters["fetch_limit"] == 21
    response = build_response(
        plan,
        [
            {
                "patient_id": "Patient/p",
                "medication_id": "MedicationRequest/m",
                "medication_code": "6809",
                "medication_status": "active",
                "authored_on": "2025-02-01",
            }
        ],
        "demo",
        query,
        parameters,
    )
    facts = next(
        item["facts"] for item in response["evidence"] if item["id"] == "MedicationRequest/m"
    )
    assert facts == {
        "MedicationRequest.medicationCodeableConcept.coding[0].code": "6809",
        "MedicationRequest.status": "active",
        "MedicationRequest.authoredOn": "2025-02-01",
        "MedicationRequest.subject.reference": "Patient/p",
    }
    assert "adherence" in response["answer"]


def test_patient_lab_history_excludes_nonfinal_results_and_has_exact_lab_facts() -> None:
    plan = QueryPlan(intent="patient_lab_history", patient_id="Patient/p", lab_code="4548-4")
    query, parameters = compile_plan(plan, offset=2)
    assert "o.status IN ['final', 'amended', 'corrected']" in query
    assert "o.code_coding_0_code = $lab_code" in query
    assert "observed_at IS NULL ASC" in query
    assert "nanosecond DESC, observation_id ASC" in query
    assert parameters["patient_id"] == "Patient/p" and parameters["offset"] == 2
    response = build_response(
        plan,
        [
            {
                "patient_id": "Patient/p",
                "observation_id": "Observation/o",
                "lab_code": "4548-4",
                "lab_status": "corrected",
                "value": 7.2,
                "unit": "%",
                "observed_at": "2025-02-01T12:00:00Z",
            }
        ],
        "demo",
        query,
        parameters,
    )
    facts = next(item["facts"] for item in response["evidence"] if item["id"] == "Observation/o")
    assert facts["Observation.valueQuantity.value"] == 7.2
    assert facts["Observation.effectiveDateTime"] == "2025-02-01T12:00:00Z"
    assert facts["Observation.status"] == "corrected"


@pytest.mark.parametrize(
    "payload",
    [
        {"intent": "medication_cohort"},
        {"intent": "medication_cohort", "medication_code": "6809", "threshold": 8.0},
        {"intent": "patient_lab_history", "lab_code": "4548-4"},
        {"intent": "patient_lab_history", "patient_id": "Patient/p", "medication_code": "6809"},
    ],
)
def test_new_intents_reject_missing_or_unowned_filters(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        QueryPlan.model_validate(payload)


def test_resolved_absolute_reference_cites_the_raw_source_and_hides_internal_columns() -> None:
    source_reference = "http://example.test/fhir/Patient/p"
    row = {
        "patient_id": "Patient/p",
        "observation_id": "Observation/o",
        "lab_code": "4548-4",
        "value": 8.2,
        "_observation_subject_reference": source_reference,
    }
    response = build_response(
        QueryPlan(intent="patient_lab_history", patient_id="Patient/p"), [row], "demo", "query", {}
    )
    observation = next(item for item in response["evidence"] if item["id"] == "Observation/o")
    assert observation["facts"]["Observation.subject.reference"] == source_reference
    assert response["results"] == [
        {
            "patient_id": "Patient/p",
            "observation_id": "Observation/o",
            "lab_code": "4548-4",
            "value": 8.2,
        }
    ]


def test_patient_history_filters_resolved_associations_but_returns_raw_fhir_references() -> None:
    query, _ = compile_plan(QueryPlan(intent="patient_history", patient_id="Patient/p"))
    assert "coalesce(r.subject_reference_canonical, r.subject_reference) = p.id" in query
    assert "coalesce(r.patient_reference_canonical, r.patient_reference) = p.id" in query
    assert "r.subject_reference AS _resource_subject_reference" in query
    assert "r.patient_reference AS _resource_patient_reference" in query


def test_combined_latest_lab_condition_returns_raw_reference_for_each_supporting_fact() -> None:
    plan = QueryPlan(
        intent="latest_lab_medication",
        lab_code="4548-4",
        medication_code="6809",
        threshold=8.0,
        unit="%",
        condition_code="44054006",
    )
    query, _ = compile_plan(plan)
    assert "c.subject_reference AS _condition_subject_reference" in query
    assert "o.subject_reference AS _observation_subject_reference" in query
    assert "m.subject_reference AS _medication_subject_reference" in query


@pytest.mark.parametrize(
    "plan,row,identifier,path,value",
    [
        (
            QueryPlan(intent="patient_lab_history", patient_id="Patient/p"),
            {"observation_id": "Observation/o", "lab_name": "Hemoglobin A1c"},
            "Observation/o",
            "Observation.code.coding[0].display",
            "Hemoglobin A1c",
        ),
        (
            QueryPlan(intent="medication_cohort", medication_code="6809"),
            {"medication_id": "MedicationRequest/m", "medication_name": "Metformin"},
            "MedicationRequest/m",
            "MedicationRequest.medicationCodeableConcept.coding[0].display",
            "Metformin",
        ),
        (
            QueryPlan(intent="condition_cohort", condition_code="44054006"),
            {"condition_id": "Condition/c", "condition_name": "Type 2 diabetes"},
            "Condition/c",
            "Condition.code.coding[0].display",
            "Type 2 diabetes",
        ),
        (
            QueryPlan(intent="patient_history", patient_id="Patient/p"),
            {
                "resource_id": "Encounter/e",
                "resource_type": "Encounter",
                "display": "Ambulatory",
                "_resource_type_display": "Ambulatory",
            },
            "Encounter/e",
            "Encounter.type[0].coding[0].display",
            "Ambulatory",
        ),
    ],
)
def test_displayed_source_names_have_exact_citation_fields(
    plan: QueryPlan, row: dict[str, object], identifier: str, path: str, value: str
) -> None:
    response = build_response(plan, [{"patient_id": "Patient/p", **row}], "demo", "query", {})
    facts = next(item["facts"] for item in response["evidence"] if item["id"] == identifier)
    assert facts[path] == value
