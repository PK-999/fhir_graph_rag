"""Independent NDJSON oracle and evidence verification for the portfolio evaluator."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest
from scripts.evaluate import build_cases, load_dataset, main, run_evaluation

Resource = dict[str, Any]


def patient(identifier: str) -> Resource:
    return {
        "resourceType": "Patient",
        "id": identifier,
        "name": [{"given": [identifier.title()], "family": "Example"}],
    }


def observation(
    identifier: str,
    value: object = 9.0,
    *,
    patient_id: str = "p",
    timestamp: str = "2025-02-01T12:00:00Z",
    status: str = "final",
    unit: str = "%",
) -> Resource:
    quantity: Resource = {"unit": unit}
    if value is not None:
        quantity["value"] = value
    return {
        "resourceType": "Observation",
        "id": identifier,
        "subject": {"reference": f"Patient/{patient_id}"},
        "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4"}]},
        "effectiveDateTime": timestamp,
        "status": status,
        "valueQuantity": quantity,
    }


def medication(identifier: str, *, status: str = "active", patient_id: str = "p") -> Resource:
    return {
        "resourceType": "MedicationRequest",
        "id": identifier,
        "subject": {"reference": f"Patient/{patient_id}"},
        "medicationCodeableConcept": {"coding": [{"code": "6809"}]},
        "status": status,
    }


def condition(identifier: str, *, patient_id: str = "p", code: str = "44054006") -> Resource:
    return {
        "resourceType": "Condition",
        "id": identifier,
        "subject": {"reference": f"Patient/{patient_id}"},
        "code": {"coding": [{"code": code}]},
    }


def write_dataset(directory: Path, resources: list[Resource]) -> Path:
    ndjson = directory / "ndjson"
    ndjson.mkdir(parents=True)
    with (ndjson / "resources.ndjson").open("w") as stream:
        for resource in resources:
            stream.write(json.dumps(resource) + "\n")
    return directory


def expected_case(directory: Path, name: str = "latest_lab_medication_all") -> dict[str, Any]:
    return next(case.expected for case in build_cases(load_dataset(directory)) if case.name == name)


@pytest.mark.parametrize(
    ("latest", "medication_status", "expected_ids"),
    [
        (observation("new", 7.0), "active", []),
        (observation("new", None), "active", []),
        (observation("new", 9.0, unit="mmol/mol"), "active", []),
        (observation("new", "9.0"), "active", []),
        (observation("new", True), "active", []),
        (observation("new", 8.0), "active", []),
        (observation("new", 9.0), "completed", []),
        (observation("new", 9.0), "stopped", []),
        (observation("new", 9.0, status="amended"), "active", ["Patient/p"]),
        (observation("new", 9.0, status="corrected"), "active", ["Patient/p"]),
        (observation("new", 7.0, status="preliminary"), "active", ["Patient/p"]),
    ],
)
def test_latest_lab_selection_precedes_value_unit_and_medication_filtering(
    tmp_path: Path, latest: Resource, medication_status: str, expected_ids: list[str]
) -> None:
    root = write_dataset(
        tmp_path,
        [
            patient("p"),
            observation("old", 10.0, timestamp="2025-01-01T12:00:00Z"),
            latest,
            medication("metformin", status=medication_status),
        ],
    )
    assert expected_case(root)["patient_ids"] == expected_ids


def test_timestamp_tie_uses_descending_canonical_observation_id(tmp_path: Path) -> None:
    root = write_dataset(
        tmp_path,
        [patient("p"), observation("a", 9.0), observation("z", 7.0), medication("m")],
    )
    assert expected_case(root)["patient_ids"] == []


def test_latest_timestamp_is_chronological_across_timezones(tmp_path: Path) -> None:
    root = write_dataset(
        tmp_path,
        [
            patient("p"),
            observation("z", 9.0, timestamp="2025-02-01T14:00:00+03:00"),
            observation("a", 7.0, timestamp="2025-02-01T12:00:00Z"),
            medication("m"),
        ],
    )
    assert expected_case(root)["patient_ids"] == []


def test_duplicate_medications_return_one_patient_and_lowest_source_id(tmp_path: Path) -> None:
    root = write_dataset(
        tmp_path,
        [patient("p"), observation("lab"), medication("z"), medication("a")],
    )
    expected = expected_case(root)
    assert expected["patient_ids"] == ["Patient/p"]
    assert expected["rows"] == [
        {
            "patient_id": "Patient/p",
            "given": "P",
            "family": "Example",
            "name": "P Example",
            "observation_id": "Observation/lab",
            "medication_id": "MedicationRequest/a",
            "value": 9.0,
            "unit": "%",
            "observed_at": "2025-02-01T12:00:00Z",
            "medication_status": "active",
            "lab_code": "4548-4",
            "lab_name": None,
            "lab_status": "final",
            "medication_code": "6809",
        }
    ]
    assert {item["id"] for item in expected["evidence"]} == {
        "Patient/p",
        "Observation/lab",
        "MedicationRequest/a",
    }
    lab = next(item for item in expected["evidence"] if item["type"] == "Observation")
    assert lab["facts"] == {
        "Observation.subject.reference": "Patient/p",
        "Observation.code.coding[0].code": "4548-4",
        "Observation.status": "final",
        "Observation.valueQuantity.value": 9.0,
        "Observation.valueQuantity.unit": "%",
        "Observation.effectiveDateTime": "2025-02-01T12:00:00Z",
    }
    assert lab["source_url"] == "/resources/Observation/lab"


def test_diabetes_cohort_uses_known_patients_and_lowest_condition_id(tmp_path: Path) -> None:
    root = write_dataset(
        tmp_path,
        [
            patient("p"),
            patient("other"),
            condition("z"),
            condition("a"),
            condition("wrong", patient_id="other", code="wrong"),
            condition("unknown", patient_id="unregistered"),
        ],
    )
    expected = expected_case(root, "condition_cohort_all")
    assert expected["patient_ids"] == ["Patient/p"]
    assert expected["rows"] == [
        {
            "patient_id": "Patient/p",
            "given": "P",
            "family": "Example",
            "name": "P Example",
            "condition_id": "Condition/a",
            "condition_code": "44054006",
            "condition_name": None,
        }
    ]
    assert {item["id"] for item in expected["evidence"]} == {"Patient/p", "Condition/a"}


def test_list_five_and_full_list_have_complete_expected_canonical_order(tmp_path: Path) -> None:
    root = write_dataset(tmp_path, [patient(str(index)) for index in reversed(range(7))])
    cases = {case.name: case for case in build_cases(load_dataset(root))}
    assert cases["patient_list_example"].expected["patient_ids"] == [
        "Patient/0",
        "Patient/1",
        "Patient/2",
        "Patient/3",
        "Patient/4",
        "Patient/5",
        "Patient/6",
    ]
    assert "plan" not in cases["patient_list_example"].request
    assert cases["patient_list_all"].request["plan"] == {"intent": "patient_list", "limit": 100}
    assert cases["patient_list_all"].expected["patient_ids"] == [f"Patient/{i}" for i in range(7)]


def test_zero_matches_require_empty_rows_and_evidence(tmp_path: Path) -> None:
    root = write_dataset(tmp_path, [patient("p")])
    expected = expected_case(root)
    assert expected == {"status": "answered", "patient_ids": [], "rows": [], "evidence": []}


def test_history_oracle_orders_real_event_times_across_offsets_and_leaves_undated_last(
    tmp_path: Path,
) -> None:
    root = write_dataset(
        tmp_path,
        [
            patient("p"),
            patient("z-other"),
            observation("offset", timestamp="2025-02-01T14:00:00+03:00"),
            observation("utc", timestamp="2025-02-01T12:00:00Z"),
            {
                "resourceType": "Encounter",
                "id": "e",
                "subject": {"reference": "Patient/p"},
                "period": {"start": "2025-02-02T08:00:00Z"},
                "status": "finished",
            },
            {**condition("c"), "recordedDate": "2025-01-01T08:00:00Z"},
            medication("undated"),
            observation("unrelated", patient_id="z-other", timestamp="2025-03-01T00:00:00Z"),
        ],
    )
    history = expected_case(root, "patient_history_example")
    assert [row["resource_id"] for row in history["rows"]] == [
        "Encounter/e",
        "Observation/utc",
        "Observation/offset",
        "Condition/c",
        "MedicationRequest/undated",
    ]
    assert history["patient_ids"] == ["Patient/p"] * 5
    citations = {item["id"]: item for item in history["evidence"]}
    assert citations["Encounter/e"]["facts"]["Encounter.period.start"] == "2025-02-02T08:00:00Z"
    assert citations["Condition/c"]["facts"]["Condition.recordedDate"] == "2025-01-01T08:00:00Z"


def test_history_without_records_retains_patient_evidence_and_missing_patient_has_none(
    tmp_path: Path,
) -> None:
    root = write_dataset(tmp_path, [patient("p")])
    history = expected_case(root, "patient_history_example")
    assert history["patient_ids"] == ["Patient/p"]
    assert history["rows"][0]["resource_id"] is None
    assert [item["id"] for item in history["evidence"]] == ["Patient/p"]
    missing = expected_case(root, "patient_history_missing")
    assert missing["rows"] == [] and missing["evidence"] == []


def test_history_includes_standard_allergy_patient_reference(tmp_path: Path) -> None:
    root = write_dataset(
        tmp_path,
        [
            patient("p"),
            {
                "resourceType": "AllergyIntolerance",
                "id": "allergy",
                "patient": {"reference": "Patient/p"},
                "recordedDate": "2025-03-01T08:00:00Z",
                "code": {"coding": [{"code": "227037002"}]},
            },
        ],
    )
    history = expected_case(root, "patient_history_example")
    assert [row["resource_id"] for row in history["rows"]] == ["AllergyIntolerance/allergy"]
    allergy = next(item for item in history["evidence"] if item["type"] == "AllergyIntolerance")
    assert allergy["facts"]["AllergyIntolerance.patient.reference"] == "Patient/p"


def test_oracle_preserves_nanoseconds_for_latest_selection_and_history_order(
    tmp_path: Path,
) -> None:
    root = write_dataset(
        tmp_path,
        [
            patient("p"),
            observation("a", 9, timestamp="2025-02-01T12:00:00.123456800Z"),
            observation("z", 7, timestamp="2025-02-01T12:00:00.123456700Z"),
            medication("m"),
        ],
    )
    assert expected_case(root)["rows"][0]["observation_id"] == "Observation/a"
    history = expected_case(root, "patient_history_example")
    assert [row["resource_id"] for row in history["rows"]][:2] == ["Observation/a", "Observation/z"]


def test_threshold_boundary_and_combined_condition_have_independent_expected_sets(
    tmp_path: Path,
) -> None:
    root = write_dataset(
        tmp_path,
        [
            patient("p"),
            patient("other"),
            observation("boundary", 8.0),
            medication("m"),
            condition("c"),
            observation("high", 9.0, patient_id="other"),
            medication("other-m", patient_id="other"),
        ],
    )
    assert expected_case(root, "latest_lab_at_least")["patient_ids"] == [
        "Patient/other",
        "Patient/p",
    ]
    assert expected_case(root, "latest_lab_with_diabetes")["patient_ids"] == []
    assert expected_case(root, "latest_lab_zero_matches")["rows"] == []


def test_larger_than_100_patient_dataset_has_complete_expectations(tmp_path: Path) -> None:
    root = write_dataset(tmp_path, [patient(str(i)) for i in range(101)])
    assert len(expected_case(root, "patient_list_all")["rows"]) == 101


def test_missing_patient_case_remains_absent_above_old_dataset_cap(tmp_path: Path) -> None:
    root = write_dataset(tmp_path, [patient(f"evaluation-missing-{i}") for i in range(101)])
    dataset = load_dataset(root)
    case = next(case for case in build_cases(dataset) if case.name == "patient_history_missing")
    assert case.expected_plan is not None
    assert case.expected_plan["patient_id"] not in dataset.resources
    assert case.expected["rows"] == []


def test_history_expectations_include_records_beyond_first_hundred(tmp_path: Path) -> None:
    root = write_dataset(tmp_path, [patient("p"), *(observation(f"o-{i:03d}") for i in range(102))])
    assert [row["resource_id"] for row in expected_case(root, "patient_history_all")["rows"]][
        -2:
    ] == [
        "Observation/o-100",
        "Observation/o-101",
    ]


def test_conflicting_duplicate_resource_is_refused(tmp_path: Path) -> None:
    root = write_dataset(tmp_path, [patient("p"), {**patient("p"), "gender": "male"}])
    with pytest.raises(ValueError, match=r"duplicate.*Patient/p"):
        load_dataset(root)


def response_for(case: Any, offset: int = 0) -> dict[str, Any]:
    limit = case.page_limit
    rows = case.expected["rows"][offset : offset + limit]
    ids = {
        row[key]
        for row in rows
        for key in ("patient_id", "resource_id", "condition_id", "observation_id", "medication_id")
        if row.get(key)
    }
    more = offset + limit < len(case.expected["rows"])
    return {
        "status": case.expected["status"],
        "results": deepcopy(rows),
        "result_count": len(rows),
        "evidence": [
            dict(deepcopy(item), label=item["id"])
            for item in case.expected["evidence"]
            if item["id"] in ids
        ],
        "plan": deepcopy(case.expected_plan),
        "pagination": {
            "offset": offset,
            "limit": limit,
            "has_more": more,
            "next_offset": offset + limit if more else None,
        }
        if case.expected["status"] == "answered"
        else None,
    }


def evaluation_transport(
    cases: list[Any],
    *,
    sources: dict[str, Resource],
    mutation: str | None = None,
    use_summary_model: bool = False,
) -> httpx.MockTransport:
    remaining = iter(cases)
    active: Any = None

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal active
        if request.method == "GET":
            identifier = request.url.path.removeprefix("/api/v1/resources/")
            source = deepcopy(sources[identifier])
            if mutation == "late_source_drift" and identifier == "Observation/o-100":
                source["valueQuantity"]["value"] = 99.0
            if identifier == "Observation/lab":
                if mutation == "source_missing":
                    return httpx.Response(404, json={"detail": "Source missing"})
                if mutation == "source_drift":
                    source["valueQuantity"]["value"] = 99.0
                if mutation == "source_identity":
                    source["id"] = "invented"
                if mutation == "source_patient":
                    source["subject"]["reference"] = "Patient/someone-else"
                if mutation == "source_display":
                    source["code"]["coding"][0]["display"] = "Invented diagnosis"
            return httpx.Response(200, json=source)
        body = json.loads(request.content)
        offset = body.get("offset", 0)
        if offset == 0:
            active = next(remaining)
        case = active
        assert request.url.path == "/api/v1/assistant/query"
        expected_body = (
            case.request
            if offset == 0
            else {
                "query": case.request["query"],
                "plan": response_for(case)["plan"],
                "offset": offset,
            }
        )
        if use_summary_model:
            expected_body = {**expected_body, "use_summary_model": True}
        assert body == expected_body
        payload = response_for(case, offset)
        if use_summary_model:
            first_fact = next(
                (
                    (item["id"], path, value)
                    for item in payload["evidence"]
                    for path, value in item["facts"].items()
                ),
                None,
            )
            claims = (
                [{"evidence_id": first_fact[0], "field": first_fact[1], "value": first_fact[2]}]
                if first_fact
                else []
            )
            payload.update(
                claims=claims,
                summary=(
                    f"{first_fact[0]}: {first_fact[1]} = {json.dumps(first_fact[2], ensure_ascii=False)}."
                    if first_fact
                    else None
                ),
                summary_metadata={
                    "requested": True,
                    "status": "validated" if claims else "no_evidence",
                    "model": "local" if claims else None,
                    "claim_count": len(claims),
                },
            )
            if claims and case.name == "patient_lab_history_all":
                if mutation == "claim_id":
                    claims[0]["evidence_id"] = "Patient/invented"
                elif mutation == "claim_field":
                    claims[0]["field"] = "Patient.diagnosis"
                elif mutation == "claim_value":
                    claims[0]["value"] = "Invented clinical fact"
                elif mutation == "claim_prose":
                    claims[0]["text"] = "Start insulin"
                elif mutation == "claim_duplicate":
                    claims.append(deepcopy(claims[0]))
                elif mutation == "summary_prose":
                    payload["summary"] = "Start insulin"
                elif mutation == "summary_missing":
                    payload.pop("summary")
                elif mutation == "summary_metadata":
                    payload["summary_metadata"]["claim_count"] = 999
                elif mutation == "summary_unavailable":
                    payload.update(claims=[], summary=None)
                    payload["summary_metadata"].update(status="unavailable", claim_count=0)
        if mutation == "page_failure" and offset:
            return httpx.Response(503, json={"detail": "Graph unavailable"})
        if mutation == "premature_end" and case.name == "patient_list_all":
            payload["pagination"].update(has_more=False, next_offset=None)
        if (
            mutation == "nonadvancing_offset"
            and payload["pagination"]
            and payload["pagination"]["has_more"]
        ):
            payload["pagination"]["next_offset"] = offset
        if mutation == "repeat_page" and offset:
            original = response_for(case)
            payload.update(
                results=original["results"],
                evidence=original["evidence"],
                result_count=original["result_count"],
            )
        if mutation == "missing_pagination":
            payload.pop("pagination", None)
        if mutation == "changed_plan" and offset:
            payload["plan"] = {**payload["plan"], "intent": "condition_cohort"}
        if mutation == "invalid_first_plan" and case.expected["status"] == "answered":
            payload["plan"] = {
                "intent": "invented",
                "limit": payload["pagination"]["limit"],
                "offset": True,
            }
        if (
            mutation in {"cohort_name", "cohort_code", "cohort_display"}
            and case.name == "condition_cohort_all"
            and offset
        ):
            field = {
                "cohort_name": "name",
                "cohort_code": "condition_code",
                "cohort_display": "condition_name",
            }[mutation]
            payload["results"][0][field] = "Invented fact"
        if (
            mutation in {"lab_code", "lab_status", "lab_name", "medication_code"}
            and case.name == "latest_lab_medication_all"
        ):
            payload["results"][0][mutation] = "Invented fact"
        if mutation == "history_display" and case.name == "patient_history_all":
            payload["results"][0]["display"] = "Invented diagnosis"
        if mutation == "wrong_fact" and case.name == "latest_lab_medication_all":
            lab = next(item for item in payload["evidence"] if item["type"] == "Observation")
            lab["facts"]["Observation.valueQuantity.value"] = 100.0
        elif mutation == "unknown_resource" and case.name == "latest_lab_medication_all":
            payload["evidence"][0]["id"] = "Patient/invented"
        elif mutation == "wrong_support" and case.name == "latest_lab_medication_all":
            payload["results"][0]["medication_id"] = "MedicationRequest/z"
        elif mutation == "duplicate_row" and case.name == "latest_lab_medication_all":
            payload["results"].append(payload["results"][0])
            payload["result_count"] += 1
        elif mutation == "bad_abstention" and case.name == "unsupported_treatment":
            payload["evidence"] = [{"id": "Patient/p"}]
        elif mutation == "wrong_source_url" and case.name == "patient_list_all":
            payload["evidence"][0]["source_url"] = "/resources/Patient/invented"
        elif mutation == "wrong_history_order" and case.name == "patient_history_all":
            payload["results"].reverse()
        elif mutation == "wrong_history_value" and case.name == "patient_history_all":
            payload["results"][0]["value"] = 99.0
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handle)


def test_evaluation_compares_exact_known_ids_and_source_facts(tmp_path: Path) -> None:
    root = write_dataset(
        tmp_path, [patient("p"), condition("c"), observation("lab"), medication("m")]
    )
    dataset = load_dataset(root)
    cases = build_cases(dataset)
    with httpx.Client(transport=evaluation_transport(cases, sources=dataset.resources)) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    assert report["status"] == "pass"
    assert {"patient_history_example", "patient_history_all", "latest_lab_with_diabetes"}.issubset(
        {case["name"] for case in report["cases"]}
    )
    assert all(case["status"] == "pass" for case in report["cases"])
    assert report["patient_count"] == 1
    assert report["source_checks"]["total"] == 4
    assert report["source_checks"]["passed"] == 4


def test_evaluation_traverses_every_patient_and_history_page(tmp_path: Path) -> None:
    dataset = load_dataset(
        write_dataset(
            tmp_path,
            [
                patient("p"),
                *(patient(f"z-{i:03d}") for i in range(100)),
                *(observation(f"o-{i:03d}") for i in range(102)),
            ],
        )
    )
    with httpx.Client(
        transport=evaluation_transport(build_cases(dataset), sources=dataset.resources)
    ) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    assert report["status"] == "pass"
    cases = {case["name"]: case for case in report["cases"]}
    assert cases["patient_list_all"]["actual"]["result_count"] == 101
    assert cases["patient_list_all"]["page_count"] == 2
    assert cases["patient_history_all"]["actual"]["result_count"] == 102
    assert cases["patient_history_all"]["page_count"] == 2
    assert (
        cases["patient_history_all"]["actual"]["results"][-1]["resource_id"] == "Observation/o-101"
    )
    assert report["source_checks"]["total"] == 203


@pytest.mark.parametrize(
    "mutation",
    [
        "premature_end",
        "nonadvancing_offset",
        "repeat_page",
        "page_failure",
        "missing_pagination",
        "changed_plan",
    ],
)
def test_evaluation_rejects_incomplete_or_invalid_page_traversal(
    tmp_path: Path, mutation: str
) -> None:
    dataset = load_dataset(write_dataset(tmp_path, [patient(f"p-{i:03d}") for i in range(101)]))
    with httpx.Client(
        transport=evaluation_transport(
            build_cases(dataset), sources=dataset.resources, mutation=mutation
        )
    ) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    assert report["status"] == "fail"
    assert any(case["errors"] for case in report["cases"])


def test_later_page_fhir_source_drift_fails_evaluation(tmp_path: Path) -> None:
    dataset = load_dataset(
        write_dataset(tmp_path, [patient("p"), *(observation(f"o-{i:03d}") for i in range(102))])
    )
    with httpx.Client(
        transport=evaluation_transport(
            build_cases(dataset), sources=dataset.resources, mutation="late_source_drift"
        )
    ) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    case = next(case for case in report["cases"] if case["name"] == "patient_history_example")
    assert case["status"] == "fail"
    assert case["page_count"] == 6
    assert any("Observation/o-100" in error for error in case["errors"])


def test_invalid_first_plan_fails_even_when_rows_and_evidence_are_correct(tmp_path: Path) -> None:
    dataset = load_dataset(write_dataset(tmp_path, [patient("p")]))
    with httpx.Client(
        transport=evaluation_transport(
            build_cases(dataset), sources=dataset.resources, mutation="invalid_first_plan"
        )
    ) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    assert report["status"] == "fail"
    assert any("plan" in error.lower() for case in report["cases"] for error in case["errors"])


@pytest.mark.parametrize("mutation", ["cohort_name", "cohort_code", "cohort_display"])
def test_later_page_displayed_source_fact_drift_fails_evaluation(
    tmp_path: Path, mutation: str
) -> None:
    resources = [patient(f"p-{i:03d}") for i in range(101)] + [
        condition(f"c-{i:03d}", patient_id=f"p-{i:03d}") for i in range(101)
    ]
    dataset = load_dataset(write_dataset(tmp_path, resources))
    with httpx.Client(
        transport=evaluation_transport(
            build_cases(dataset), sources=dataset.resources, mutation=mutation
        )
    ) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    case = next(case for case in report["cases"] if case["name"] == "condition_cohort_all")
    assert case["status"] == "fail"
    assert case["errors"]


def test_exact_page_boundary_does_not_request_an_empty_page(tmp_path: Path) -> None:
    dataset = load_dataset(write_dataset(tmp_path, [patient(f"p-{i:03d}") for i in range(100)]))
    with httpx.Client(
        transport=evaluation_transport(build_cases(dataset), sources=dataset.resources)
    ) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    case = next(case for case in report["cases"] if case["name"] == "patient_list_all")
    assert report["status"] == "pass"
    assert case["page_count"] == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_fact",
        "unknown_resource",
        "wrong_support",
        "duplicate_row",
        "bad_abstention",
        "wrong_source_url",
        "source_drift",
        "source_identity",
        "source_missing",
        "source_patient",
        "wrong_history_order",
        "wrong_history_value",
        "lab_code",
        "lab_status",
        "lab_name",
        "medication_code",
        "history_display",
    ],
)
def test_evaluation_fails_for_ungrounded_or_duplicate_results(
    tmp_path: Path, mutation: str
) -> None:
    root = write_dataset(
        tmp_path, [patient("p"), condition("c"), observation("lab"), medication("m")]
    )
    dataset = load_dataset(root)
    cases = build_cases(dataset)
    with httpx.Client(
        transport=evaluation_transport(cases, sources=dataset.resources, mutation=mutation)
    ) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    assert report["status"] == "fail"
    assert any(case["status"] == "fail" and case["errors"] for case in report["cases"])


def test_network_errors_are_recorded_for_every_case(tmp_path: Path) -> None:
    dataset = load_dataset(write_dataset(tmp_path, [patient("p")]))

    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with httpx.Client(transport=httpx.MockTransport(unavailable)) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    assert report["status"] == "fail"
    assert "patient_history_example" in {case["name"] for case in report["cases"]}
    assert all("connection refused" in case["errors"][0] for case in report["cases"])


def test_cli_writes_failure_report_and_returns_nonzero_for_ambiguous_source(tmp_path: Path) -> None:
    root = write_dataset(tmp_path / "input", [patient("p"), {**patient("p"), "gender": "male"}])
    output = tmp_path / "reports" / "evaluation.json"
    assert (
        main(["--input", str(root), "--api-url", "http://demo/api/v1", "--output", str(output)])
        == 1
    )
    report = json.loads(output.read_text())
    assert report["status"] == "fail"
    assert "duplicate" in report["error"]


def test_raw_oracle_medication_cohort_preserves_active_source_id_and_authored_date(
    tmp_path: Path,
) -> None:
    resources = [
        patient("p"),
        patient("other"),
        patient("stopped"),
        {**medication("a"), "authoredOn": "2025-02-01"},
        medication("z"),
        medication("other-m", patient_id="other"),
        medication("stopped-m", patient_id="stopped", status="stopped"),
        condition("c"),
    ]
    root = write_dataset(tmp_path, resources)
    cohort = expected_case(root, "medication_cohort_all")
    assert cohort["patient_ids"] == ["Patient/other", "Patient/p"]
    selected = next(row for row in cohort["rows"] if row["patient_id"] == "Patient/p")
    assert selected["medication_id"] == "MedicationRequest/a"
    assert selected["authored_on"] == "2025-02-01"
    facts = next(
        item["facts"] for item in cohort["evidence"] if item["id"] == "MedicationRequest/a"
    )
    assert facts["MedicationRequest.authoredOn"] == "2025-02-01"
    assert expected_case(root, "medication_cohort_with_diabetes")["patient_ids"] == ["Patient/p"]


def test_raw_oracle_lab_history_retains_values_dates_units_and_filters_status(
    tmp_path: Path,
) -> None:
    root = write_dataset(
        tmp_path,
        [
            patient("p"),
            observation("old", 7.1, timestamp="2025-01-01T00:00:00Z"),
            observation("corrected", 8.2, status="corrected"),
            observation("preliminary", 99.0, status="preliminary"),
            observation("wrong-patient", 88.0, patient_id="someone-else"),
            {**observation("other-code", 12.0), "code": {"coding": [{"code": "2345-7"}]}},
        ],
    )
    expected = expected_case(root, "patient_lab_history_all")
    assert [row["observation_id"] for row in expected["rows"]] == [
        "Observation/corrected",
        "Observation/other-code",
        "Observation/old",
    ]
    assert [(row["value"], row["unit"], row["observed_at"]) for row in expected["rows"]] == [
        (8.2, "%", "2025-02-01T12:00:00Z"),
        (12.0, "%", "2025-02-01T12:00:00Z"),
        (7.1, "%", "2025-01-01T00:00:00Z"),
    ]
    assert [
        row["observation_id"]
        for row in expected_case(root, "patient_hba1c_history_example")["rows"]
    ] == ["Observation/corrected", "Observation/old"]


def test_raw_oracle_new_intents_paginate_beyond_one_hundred(tmp_path: Path) -> None:
    dataset = load_dataset(
        write_dataset(
            tmp_path,
            [
                patient("p"),
                *(observation(f"o-{i:03d}") for i in range(102)),
                *(patient(f"z-{i:03d}") for i in range(100)),
                medication("m"),
                *(medication(f"m-{i:03d}", patient_id=f"z-{i:03d}") for i in range(100)),
            ],
        )
    )
    with httpx.Client(
        transport=evaluation_transport(build_cases(dataset), sources=dataset.resources)
    ) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    cases = {case["name"]: case for case in report["cases"]}
    assert report["status"] == "pass"
    assert cases["medication_cohort_all"]["actual"]["result_count"] == 101
    assert cases["medication_cohort_all"]["page_count"] == 2
    assert cases["patient_lab_history_all"]["actual"]["result_count"] == 102
    assert cases["patient_lab_history_all"]["page_count"] == 2


def test_live_evaluation_includes_complete_question_paraphrases_and_new_filter_abstentions(
    tmp_path: Path,
) -> None:
    dataset = load_dataset(
        write_dataset(tmp_path, [patient("p"), medication("m"), observation("o")])
    )
    names = {case.name for case in build_cases(dataset)}
    assert {
        "patient_list_paraphrase",
        "condition_cohort_paraphrase",
        "latest_lab_paraphrase",
        "patient_history_paraphrase",
        "medication_cohort_paraphrase",
        "patient_lab_history_paraphrase",
        "unsupported_medication_age_filter",
        "unsupported_lab_date_filter",
    }.issubset(names)


def test_optional_summary_evaluation_validates_claims_against_raw_fhir_and_preserves_flag_across_pages(
    tmp_path: Path,
) -> None:
    dataset = load_dataset(
        write_dataset(tmp_path, [patient("p"), *(observation(f"o-{i:03d}") for i in range(102))])
    )
    with httpx.Client(
        transport=evaluation_transport(
            build_cases(dataset), sources=dataset.resources, use_summary_model=True
        )
    ) as client:
        report = run_evaluation(
            dataset, "http://demo/api/v1", client=client, use_summary_model=True
        )
    assert report["status"] == "pass"
    assert report["summary_model_requested"] is True
    case = next(case for case in report["cases"] if case["name"] == "patient_lab_history_all")
    assert case["page_count"] == 2
    assert all(page["summary_metadata"]["status"] == "validated" for page in case["pages"])


@pytest.mark.parametrize(
    "mutation",
    [
        "claim_id",
        "claim_field",
        "claim_value",
        "claim_prose",
        "claim_duplicate",
        "summary_prose",
        "summary_missing",
        "summary_metadata",
        "summary_unavailable",
    ],
)
def test_optional_summary_evaluation_rejects_unverified_claims_and_rendered_prose(
    tmp_path: Path, mutation: str
) -> None:
    dataset = load_dataset(write_dataset(tmp_path, [patient("p"), observation("o")]))
    with httpx.Client(
        transport=evaluation_transport(
            build_cases(dataset),
            sources=dataset.resources,
            use_summary_model=True,
            mutation=mutation,
        )
    ) as client:
        report = run_evaluation(
            dataset, "http://demo/api/v1", client=client, use_summary_model=True
        )
    case = next(case for case in report["cases"] if case["name"] == "patient_lab_history_all")
    assert report["status"] == "fail" and case["status"] == "fail"
    assert any("claim" in error.lower() or "summary" in error.lower() for error in case["errors"])


def test_cli_summary_flag_exercises_the_local_model_claim_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = write_dataset(tmp_path / "input", [patient("p"), observation("o")])
    dataset = load_dataset(root)
    client = httpx.Client(
        transport=evaluation_transport(
            build_cases(dataset), sources=dataset.resources, use_summary_model=True
        )
    )
    monkeypatch.setattr("scripts.evaluate.httpx.Client", lambda **kwargs: client)
    output = tmp_path / "summary-evaluation.json"
    assert (
        main(
            [
                "--input",
                str(root),
                "--api-url",
                "http://demo/api/v1",
                "--output",
                str(output),
                "--use-summary-model",
            ]
        )
        == 0
    )
    report = json.loads(output.read_text())
    assert report["status"] == "pass" and report["summary_model_requested"] is True


def test_independent_oracle_resolves_only_explicit_same_service_absolute_references(
    tmp_path: Path,
) -> None:
    base = "http://same-service.test/fhir"
    root = write_dataset(
        tmp_path,
        [
            patient("p"),
            {**observation("o"), "subject": {"reference": f"{base}/Patient/p"}},
            {**medication("m"), "subject": {"reference": f"{base}/Patient/p"}},
            {**condition("c"), "subject": {"reference": f"{base}/Patient/p"}},
            {
                **observation("foreign"),
                "subject": {"reference": "http://external.test/fhir/Patient/p"},
            },
        ],
    )
    dataset = load_dataset(root, fhir_base_url=base)
    cases = build_cases(dataset)
    lab = next(case for case in cases if case.name == "patient_lab_history_all")
    assert [row["observation_id"] for row in lab.expected["rows"]] == ["Observation/o"]
    facts = next(
        item["facts"] for item in lab.expected["evidence"] if item["id"] == "Observation/o"
    )
    assert facts["Observation.subject.reference"] == f"{base}/Patient/p"
    assert next(case for case in cases if case.name == "medication_cohort_all").expected[
        "patient_ids"
    ] == ["Patient/p"]
    with httpx.Client(transport=evaluation_transport(cases, sources=dataset.resources)) as client:
        assert run_evaluation(dataset, "http://demo/api/v1", client=client)["status"] == "pass"


def test_cli_explicit_fhir_base_keeps_absolute_source_representation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = "http://same-service.test/fhir"
    root = write_dataset(
        tmp_path / "input",
        [patient("p"), {**observation("o"), "subject": {"reference": f"{base}/Patient/p"}}],
    )
    dataset = load_dataset(root, fhir_base_url=base)
    client = httpx.Client(
        transport=evaluation_transport(build_cases(dataset), sources=dataset.resources)
    )
    monkeypatch.setattr("scripts.evaluate.httpx.Client", lambda **kwargs: client)
    output = tmp_path / "absolute-evaluation.json"
    assert (
        main(
            [
                "--input",
                str(root),
                "--api-url",
                "http://demo/api/v1",
                "--output",
                str(output),
                "--fhir-base-url",
                base,
            ]
        )
        == 0
    )
    report = json.loads(output.read_text())
    assert report["status"] == "pass" and report["fhir_base_url"] == base


def test_evaluation_can_select_exact_named_cases_without_changing_default_coverage(
    tmp_path: Path,
) -> None:
    dataset = load_dataset(write_dataset(tmp_path, [patient("p"), observation("o")]))
    selected = {"patient_list_example", "patient_hba1c_history_example"}
    cases = [case for case in build_cases(dataset) if case.name in selected]
    with httpx.Client(
        transport=evaluation_transport(cases, sources=dataset.resources, use_summary_model=True)
    ) as client:
        report = run_evaluation(
            dataset, "http://demo/api/v1", client=client, use_summary_model=True, case_ids=selected
        )
    assert report["status"] == "pass"
    assert {case["name"] for case in report["cases"]} == selected
    assert set(report["selected_case_ids"]) == selected
    assert len(build_cases(dataset)) == 33


@pytest.mark.parametrize("case_ids", [set(), {"invented"}, {"patient_list_example", "invented"}])
def test_invalid_evaluation_case_selection_is_rejected_before_network(
    tmp_path: Path, case_ids: set[str]
) -> None:
    dataset = load_dataset(write_dataset(tmp_path, [patient("p")]))

    def forbidden(request: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid coverage selection must fail before HTTP requests")

    with (
        httpx.Client(transport=httpx.MockTransport(forbidden)) as client,
        pytest.raises(ValueError, match="case"),
    ):
        run_evaluation(dataset, "http://demo/api/v1", client=client, case_ids=case_ids)


def test_cli_repeated_case_ids_select_and_report_local_summary_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = write_dataset(tmp_path / "input", [patient("p"), observation("o")])
    dataset = load_dataset(root)
    selected = {"patient_list_example", "patient_hba1c_history_example"}
    client = httpx.Client(
        transport=evaluation_transport(
            [case for case in build_cases(dataset) if case.name in selected],
            sources=dataset.resources,
            use_summary_model=True,
        )
    )
    monkeypatch.setattr("scripts.evaluate.httpx.Client", lambda **kwargs: client)
    output = tmp_path / "selected-summary-evaluation.json"
    assert (
        main(
            [
                "--input",
                str(root),
                "--api-url",
                "http://demo/api/v1",
                "--output",
                str(output),
                "--use-summary-model",
                "--case-id",
                "patient_list_example",
                "--case-id",
                "patient_hba1c_history_example",
            ]
        )
        == 0
    )
    report = json.loads(output.read_text())
    assert report["status"] == "pass" and set(report["selected_case_ids"]) == selected


def test_displayed_lab_name_drift_in_live_fhir_source_fails_evaluation(tmp_path: Path) -> None:
    source = {
        **observation("lab"),
        "code": {"coding": [{"code": "4548-4", "display": "Hemoglobin A1c"}]},
    }
    dataset = load_dataset(write_dataset(tmp_path, [patient("p"), source]))
    with httpx.Client(
        transport=evaluation_transport(
            build_cases(dataset), sources=dataset.resources, mutation="source_display"
        )
    ) as client:
        report = run_evaluation(dataset, "http://demo/api/v1", client=client)
    assert report["status"] == "fail"
    assert any(
        "Observation.code.coding[0].display" in error
        for case in report["cases"]
        for error in case["errors"]
    )
