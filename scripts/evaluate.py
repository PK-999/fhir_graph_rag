"""Compare the live portfolio assistant with an independent raw-NDJSON oracle.

Example: python scripts/evaluate.py --input /tmp/fhirgraph-demo \
    --api-url http://127.0.0.1:8010/api/v1 --output /tmp/evaluation.json

This intentionally imports no application query, graph, FHIR, or parsing helpers.
Complete result sets are checked across bounded pages, including every cited source.
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

Resource = dict[str, Any]
_MISSING = object()
_ID = re.compile(r"[A-Za-z0-9.-]{1,64}")
_PATH_PART = re.compile(r"([A-Za-z][A-Za-z0-9]*)(?:\[(\d+)\])?")
_FINAL_STATUSES = {"final", "amended", "corrected"}


@dataclass(frozen=True)
class Dataset:
    root: Path
    resources: dict[str, Resource]
    patient_ids: tuple[str, ...]
    fhir_base_url: str | None = None


@dataclass(frozen=True)
class EvaluationCase:
    name: str
    request: Resource
    expected: Resource
    page_limit: int = 20
    expected_plan: Resource | None = None


def load_dataset(root: Path, *, fhir_base_url: str | None = None) -> Dataset:
    """Read JSON directly, rejecting ambiguous IDs and silently truncated inputs."""
    if not root.is_dir():
        raise ValueError(f"Dataset directory does not exist: {root}")
    resources: dict[str, Resource] = {}
    files = sorted(root.rglob("*.ndjson"))
    if not files:
        raise ValueError(f"No NDJSON resources found under {root}")
    for source in files:
        with source.open() as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    resource = json.loads(line)
                except ValueError as exc:
                    raise ValueError(f"Invalid JSON at {source}:{line_number}: {exc}") from exc
                if not isinstance(resource, dict):
                    raise ValueError(f"Expected resource object at {source}:{line_number}")
                kind, identifier = resource.get("resourceType"), resource.get("id")
                if (
                    not isinstance(kind, str)
                    or re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", kind) is None
                    or not isinstance(identifier, str)
                    or _ID.fullmatch(identifier) is None
                ):
                    raise ValueError(f"Invalid resource type or ID at {source}:{line_number}")
                canonical_id = f"{kind}/{identifier}"
                if canonical_id in resources and resources[canonical_id] != resource:
                    raise ValueError(f"Conflicting duplicate resource {canonical_id}")
                resources[canonical_id] = resource
    patient_ids = tuple(sorted(key for key in resources if key.startswith("Patient/")))
    if not patient_ids:
        raise ValueError("Dataset contains no Patient resources")
    return Dataset(
        root.resolve(), resources, patient_ids, fhir_base_url.rstrip("/") if fhir_base_url else None
    )


def _field(resource: Resource, path: str) -> Any:
    """Resolve exact FHIR paths, including numeric array indices."""
    kind = resource["resourceType"]
    if not path.startswith(f"{kind}."):
        return _MISSING
    value: Any = resource
    for part in path.removeprefix(f"{kind}.").split("."):
        match = _PATH_PART.fullmatch(part)
        if match is None or not isinstance(value, dict) or match[1] not in value:
            return _MISSING
        value = value[match[1]]
        if match[2] is not None:
            index = int(match[2])
            if not isinstance(value, list) or index >= len(value):
                return _MISSING
            value = value[index]
    return value


def _code(resource: Resource, concept: str) -> Any:
    return _field(resource, f"{resource['resourceType']}.{concept}.coding[0].code")


def _patient(resource: Resource, dataset: Dataset | None = None) -> Any:
    association = "patient" if resource["resourceType"] == "AllergyIntolerance" else "subject"
    reference = _field(resource, f"{resource['resourceType']}.{association}.reference")
    if (
        dataset is not None
        and dataset.fhir_base_url
        and isinstance(reference, str)
        and reference.startswith(dataset.fhir_base_url + "/")
    ):
        candidate = reference[len(dataset.fhir_base_url) + 1 :]
        if (
            re.fullmatch(r"Patient/[A-Za-z0-9.-]{1,64}", candidate)
            and candidate in dataset.resources
        ):
            return candidate
    return reference


def _timestamp(resource: Resource) -> tuple[int, int] | None:
    timestamp = resource.get("effectiveDateTime")
    if not isinstance(timestamp, str):
        return None
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    fraction = re.search(r"[T ]\d{2}:\d{2}:\d{2}[.,](\d+)", timestamp)
    digits = fraction[1] if fraction else ""
    if len(digits) > 9:
        return None
    return calendar.timegm(parsed.astimezone(UTC).timetuple()), int(digits.ljust(9, "0"))


def _evidence(
    dataset: Dataset, canonical_id: str, patient_id: str, event_field: str | None = None
) -> Resource:
    resource = dataset.resources[canonical_id]
    kind = resource["resourceType"]
    paths = {
        "Patient": ["name[0].given[0]", "name[0].family"],
        "Condition": ["code.coding[0].code", "code.coding[0].display"],
        "Observation": [
            "code.coding[0].code",
            "code.coding[0].display",
            "status",
            "valueQuantity.value",
            "valueQuantity.unit",
            "effectiveDateTime",
        ],
        "MedicationRequest": ["medicationCodeableConcept.coding[0].code", "status"],
    }.get(
        kind,
        ["code.coding[0].code", "code.coding[0].display", "type[0].coding[0].display", "status"],
    )
    if kind == "MedicationRequest" and event_field:
        paths = [*paths, "medicationCodeableConcept.coding[0].display"]
    facts = {}
    for relative_path in paths:
        path = f"{kind}.{relative_path}"
        value = _field(resource, path)
        if value is not _MISSING:
            facts[path] = value
    if event_field:
        value = _field(resource, event_field)
        if value is not _MISSING:
            facts[event_field] = value
    if kind != "Patient":
        association = "patient" if kind == "AllergyIntolerance" else "subject"
        reference = _field(resource, f"{kind}.{association}.reference")
        if reference is not _MISSING:
            facts[f"{kind}.{association}.reference"] = reference
    return {
        "type": kind,
        "id": canonical_id,
        "patient_id": patient_id,
        "source_url": f"/resources/{canonical_id}",
        "facts": facts,
    }


def _expected(
    dataset: Dataset,
    intent: str,
    limit: int | None,
    *,
    condition_code: str | None = None,
    threshold: float = 8,
    comparison: str = "gt",
) -> Resource:
    associated: dict[str, list[tuple[str, Resource]]] = {}
    for identifier, resource in dataset.resources.items():
        patient = _patient(resource, dataset)
        if isinstance(patient, str):
            associated.setdefault(patient, []).append((identifier, resource))
    rows: list[Resource] = []
    evidence: list[Resource] = []
    for patient_id in dataset.patient_ids:
        support: list[str] = []
        row: Resource = _patient_row(dataset, patient_id)
        if intent == "condition_cohort":
            matches = sorted(
                identifier
                for identifier, resource in associated.get(patient_id, ())
                if resource["resourceType"] == "Condition"
                and _patient(resource, dataset) == patient_id
                and _code(resource, "code") == (condition_code or "44054006")
            )
            if not matches:
                continue
            row["condition_id"] = matches[0]
            row["condition_code"] = _code(dataset.resources[matches[0]], "code")
            row["condition_name"] = _optional_field(
                dataset.resources[matches[0]], "Condition.code.coding[0].display"
            )
            support = [matches[0]]
        elif intent == "latest_lab_medication":
            observations = [
                (timestamp, identifier, resource)
                for identifier, resource in associated.get(patient_id, ())
                if resource["resourceType"] == "Observation"
                and _patient(resource, dataset) == patient_id
                and _code(resource, "code") == "4548-4"
                and resource.get("status") in _FINAL_STATUSES
                and (timestamp := _timestamp(resource)) is not None
            ]
            if not observations:
                continue
            # Select the latest final observation before any value/unit filtering.
            _, observation_id, latest = max(observations, key=lambda item: (item[0], item[1]))
            value = _field(latest, "Observation.valueQuantity.value")
            unit = _field(latest, "Observation.valueQuantity.unit")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not {
                    "gt": value > threshold,
                    "gte": value >= threshold,
                    "lt": value < threshold,
                }[comparison]
                or unit != "%"
            ):
                continue
            medications = sorted(
                identifier
                for identifier, resource in associated.get(patient_id, ())
                if resource["resourceType"] == "MedicationRequest"
                and _patient(resource, dataset) == patient_id
                and _code(resource, "medicationCodeableConcept") == "6809"
                and resource.get("status") == "active"
            )
            if not medications:
                continue
            row.update(
                observation_id=observation_id,
                medication_id=medications[0],
                value=value,
                unit=unit,
                observed_at=latest["effectiveDateTime"],
                medication_status="active",
                lab_code=_code(latest, "code"),
                lab_name=_optional_field(latest, "Observation.code.coding[0].display"),
                lab_status=latest["status"],
                medication_code="6809",
            )
            support = [observation_id, medications[0]]
            if condition_code:
                conditions = sorted(
                    identifier
                    for identifier, resource in associated.get(patient_id, ())
                    if resource["resourceType"] == "Condition"
                    and _patient(resource, dataset) == patient_id
                    and _code(resource, "code") == condition_code
                )
                if not conditions:
                    continue
                row.update(condition_id=conditions[0], condition_code=condition_code)
                row["condition_name"] = _optional_field(
                    dataset.resources[conditions[0]], "Condition.code.coding[0].display"
                )
                support.append(conditions[0])
        elif intent == "medication_cohort":
            medications = sorted(
                identifier
                for identifier, resource in associated.get(patient_id, ())
                if resource["resourceType"] == "MedicationRequest"
                and _patient(resource, dataset) == patient_id
                and _code(resource, "medicationCodeableConcept") == "6809"
                and resource.get("status") == "active"
            )
            if not medications:
                continue
            medication_id = medications[0]
            source = dataset.resources[medication_id]
            row.update(
                medication_id=medication_id,
                medication_code="6809",
                medication_name=_optional_field(
                    source, "MedicationRequest.medicationCodeableConcept.coding[0].display"
                ),
                medication_status="active",
                authored_on=source.get("authoredOn"),
            )
            support = [medication_id]
            if condition_code:
                conditions = sorted(
                    identifier
                    for identifier, resource in associated.get(patient_id, ())
                    if resource["resourceType"] == "Condition"
                    and _patient(resource, dataset) == patient_id
                    and _code(resource, "code") == condition_code
                )
                if not conditions:
                    continue
                row.update(
                    condition_id=conditions[0],
                    condition_code=condition_code,
                    condition_name=_optional_field(
                        dataset.resources[conditions[0]], "Condition.code.coding[0].display"
                    ),
                )
                support.append(conditions[0])
        rows.append(row)
        evidence.extend(
            _evidence(
                dataset,
                key,
                patient_id,
                "MedicationRequest.authoredOn"
                if intent == "medication_cohort" and key.startswith("MedicationRequest/")
                else None,
            )
            for key in [patient_id, *support]
        )
        if len(rows) == limit:
            break
    return {
        "status": "answered",
        "patient_ids": [row["patient_id"] for row in rows],
        "rows": rows,
        "evidence": evidence,
    }


def _optional_field(resource: Resource, path: str) -> Any:
    value = _field(resource, path)
    return None if value is _MISSING else value


def _patient_row(dataset: Dataset, patient_id: str) -> Resource:
    resource = dataset.resources[patient_id]
    given = _optional_field(resource, "Patient.name[0].given[0]")
    family = _optional_field(resource, "Patient.name[0].family")
    return {
        "patient_id": patient_id,
        "given": given,
        "family": family,
        "name": f"{given or ''} {family or ''}",
    }


def _history_expected(dataset: Dataset, patient_id: str, limit: int | None) -> Resource:
    """Derive history identities and times directly from source FHIR, not graph code."""
    if patient_id not in dataset.resources:
        return {
            "status": "answered",
            "patient_ids": [],
            "rows": [],
            "evidence": [],
            "row_identity": "resource_id",
        }
    events: list[tuple[tuple[int, int] | None, Resource, Resource]] = []
    date_paths = {
        "Observation": ["effectiveDateTime"],
        "DiagnosticReport": ["effectiveDateTime"],
        "Encounter": ["period.start"],
        "Condition": ["onsetDateTime", "recordedDate"],
        "MedicationRequest": ["authoredOn"],
        "ServiceRequest": ["authoredOn"],
        "Procedure": ["performedDateTime"],
        "AllergyIntolerance": ["recordedDate"],
    }
    for identifier, resource in dataset.resources.items():
        if _patient(resource, dataset) != patient_id:
            continue
        kind = resource["resourceType"]
        event_at = None
        event_field = f"{kind}.{date_paths[kind][-1]}" if kind in date_paths else None
        for path in date_paths.get(kind, []):
            value = _field(resource, f"{kind}.{path}")
            if value is not _MISSING and value is not None:
                event_at, event_field = value, f"{kind}.{path}"
                break
        timestamp = _timestamp({"effectiveDateTime": event_at})
        source_values = {
            "code": _code(resource, "code"),
            "value": _field(resource, f"{kind}.valueQuantity.value"),
            "unit": _field(resource, f"{kind}.valueQuantity.unit"),
            "observed_at": resource.get("effectiveDateTime"),
            "status": resource.get("status"),
            "medication_code": _code(resource, "medicationCodeableConcept"),
        }
        row = {
            **_patient_row(dataset, patient_id),
            "resource_id": identifier,
            "resource_type": kind,
            "event_at": event_at,
            "event_field": event_field,
            "display": next(
                (
                    value
                    for path in (
                        "code.coding[0].display",
                        "medicationCodeableConcept.coding[0].display",
                        "type[0].coding[0].display",
                    )
                    if (value := _optional_field(resource, f"{kind}.{path}")) is not None
                ),
                kind,
            ),
            **{key: None if value is _MISSING else value for key, value in source_values.items()},
        }
        events.append((timestamp, row, _evidence(dataset, identifier, patient_id, event_field)))
    # Stable canonical-ID ties; undated resources follow every dated resource.
    events.sort(key=lambda event: event[1]["resource_id"])
    events.sort(key=lambda event: (event[0] is not None, event[0] or (0, 0)), reverse=True)
    selected = events[:limit]
    rows = [event[1] for event in selected] or [
        {
            **_patient_row(dataset, patient_id),
            **dict.fromkeys(
                (
                    "resource_id",
                    "resource_type",
                    "event_at",
                    "event_field",
                    "display",
                    "code",
                    "value",
                    "unit",
                    "observed_at",
                    "status",
                    "medication_code",
                )
            ),
        }
    ]
    return {
        "status": "answered",
        "patient_ids": [patient_id] * len(rows),
        "rows": rows,
        "evidence": [_evidence(dataset, patient_id, patient_id), *(event[2] for event in selected)],
        "row_identity": "resource_id",
    }


def build_cases(dataset: Dataset) -> list[EvaluationCase]:
    """Exercise advertised parsing plus complete result sets through explicit plans."""
    cases = []
    examples: list[tuple[str, str, int, Resource]] = [
        ("patient_list", "List five patients", 5, {}),
        (
            "condition_cohort",
            "Find patients with type 2 diabetes",
            20,
            {"condition_code": "44054006"},
        ),
        (
            "latest_lab_medication",
            "Find patients whose latest HbA1c is above 8% with active Metformin",
            20,
            {
                "lab_code": "4548-4",
                "medication_code": "6809",
                "threshold": 8,
                "comparison": "gt",
                "unit": "%",
            },
        ),
    ]
    for intent, question, limit, fields in examples:
        cases.append(
            EvaluationCase(
                f"{intent}_example",
                {"query": question},
                _expected(dataset, intent, None),
                limit,
                {"intent": intent, "limit": limit, "comparison": "gt", **fields},
            )
        )
        cases.append(
            EvaluationCase(
                f"{intent}_all",
                {"query": question, "plan": {"intent": intent, "limit": 100, **fields}},
                _expected(dataset, intent, None),
                100,
                {"intent": intent, "limit": 100, "comparison": "gt", **fields},
            )
        )
    patient_id = dataset.patient_ids[0]
    history_question = f"Show history for {patient_id}"
    history_cases: list[tuple[str, Resource, int]] = [
        ("patient_history_example", {"query": history_question}, 20),
        (
            "patient_history_all",
            {
                "query": history_question,
                "plan": {"intent": "patient_history", "patient_id": patient_id, "limit": 100},
            },
            100,
        ),
    ]
    for name, request, limit in history_cases:
        cases.append(
            EvaluationCase(
                name,
                request,
                _history_expected(dataset, patient_id, None),
                limit,
                {
                    "intent": "patient_history",
                    "patient_id": patient_id,
                    "limit": limit,
                    "comparison": "gt",
                },
            )
        )
    missing = next(
        f"Patient/evaluation-missing-{index}"
        for index in range(len(dataset.patient_ids) + 1)
        if f"Patient/evaluation-missing-{index}" not in dataset.resources
    )
    cases.append(
        EvaluationCase(
            "patient_history_missing",
            {"query": f"Show history for {missing}"},
            _history_expected(dataset, missing, 20),
            20,
            {"intent": "patient_history", "patient_id": missing, "limit": 20, "comparison": "gt"},
        )
    )
    cases.append(
        EvaluationCase(
            "hypertension_cohort",
            {
                "query": "Find patients with hypertension",
                "plan": {"intent": "condition_cohort", "condition_code": "38341003", "limit": 100},
            },
            _expected(dataset, "condition_cohort", None, condition_code="38341003"),
            100,
            {
                "intent": "condition_cohort",
                "condition_code": "38341003",
                "limit": 100,
                "comparison": "gt",
            },
        )
    )
    latest_fields = {
        "intent": "latest_lab_medication",
        "lab_code": "4548-4",
        "medication_code": "6809",
        "unit": "%",
        "limit": 100,
    }
    cases.append(
        EvaluationCase(
            "latest_lab_with_diabetes",
            {
                "query": "Latest HbA1c with active Metformin and type 2 diabetes",
                "plan": {**latest_fields, "threshold": 8, "condition_code": "44054006"},
            },
            _expected(dataset, "latest_lab_medication", None, condition_code="44054006"),
            100,
            {**latest_fields, "threshold": 8, "condition_code": "44054006", "comparison": "gt"},
        )
    )
    for name, comparison, threshold, phrase in [
        ("latest_lab_at_least", "gte", 8, "at least"),
        ("latest_lab_below", "lt", 8, "below"),
        ("latest_lab_zero_matches", "gt", 50, "above"),
    ]:
        cases.append(
            EvaluationCase(
                name,
                {
                    "query": f"Find patients whose latest HbA1c is {phrase} {threshold}% with active Metformin"
                },
                _expected(
                    dataset,
                    "latest_lab_medication",
                    None,
                    threshold=threshold,
                    comparison=comparison,
                ),
                20,
                {**latest_fields, "limit": 20, "threshold": threshold, "comparison": comparison},
            )
        )
    cases.append(
        EvaluationCase(
            "unsupported_treatment",
            {"query": "What treatment should these patients take?"},
            {"status": "abstained", "patient_ids": [], "rows": [], "evidence": []},
        )
    )
    for name, question in [
        ("unsupported_age_filter", "Find patients with type 2 diabetes who are over 65"),
        (
            "unsupported_negated_medication",
            "Find patients with type 2 diabetes without active Metformin",
        ),
        (
            "unsupported_medication_age_filter",
            "Which patients have active Metformin prescriptions who are over 65?",
        ),
        ("unsupported_lab_date_filter", f"Show HbA1c history for {patient_id} since January 2025"),
        (
            "unsupported_medication_negation",
            "Find patients on active Metformin without type 2 diabetes",
        ),
        ("unsupported_lab_threshold_filter", f"Show lab history for {patient_id} above 8%"),
    ]:
        cases.append(
            EvaluationCase(
                name,
                {"query": question},
                {"status": "abstained", "patient_ids": [], "rows": [], "evidence": []},
            )
        )
    medication_plan = {"intent": "medication_cohort", "medication_code": "6809", "comparison": "gt"}
    for name, question, limit, extra, explicit in [
        ("medication_cohort_example", "Find patients on active Metformin", 20, {}, False),
        ("medication_cohort_all", "Find patients on active Metformin", 100, {}, True),
        (
            "medication_cohort_paraphrase",
            "Which patients have active Metformin prescriptions?",
            20,
            {},
            False,
        ),
        (
            "medication_cohort_with_diabetes",
            "Find patients on active Metformin with type 2 diabetes",
            20,
            {"condition_code": "44054006"},
            False,
        ),
    ]:
        plan = {**medication_plan, "limit": limit, **extra}
        request = {"query": question, **({"plan": plan} if explicit else {})}
        cases.append(
            EvaluationCase(
                name,
                request,
                _expected(
                    dataset, "medication_cohort", None, condition_code=extra.get("condition_code")
                ),
                limit,
                plan,
            )
        )
    lab_plan = {"intent": "patient_lab_history", "patient_id": patient_id, "comparison": "gt"}
    for name, question, limit, lab_code, explicit in [
        ("patient_lab_history_example", f"Show lab history for {patient_id}", 20, None, False),
        ("patient_lab_history_all", f"Show lab history for {patient_id}", 100, None, True),
        (
            "patient_hba1c_history_example",
            f"Show HbA1c history for {patient_id}",
            20,
            "4548-4",
            False,
        ),
        (
            "patient_lab_history_paraphrase",
            f"What are the HbA1c results for {patient_id}?",
            20,
            "4548-4",
            False,
        ),
    ]:
        plan = {**lab_plan, "limit": limit, **({"lab_code": lab_code} if lab_code else {})}
        request = {"query": question, **({"plan": plan} if explicit else {})}
        cases.append(
            EvaluationCase(
                name, request, _lab_history_expected(dataset, patient_id, lab_code), limit, plan
            )
        )
    paraphrases: list[tuple[str, str, str, Resource, int, Resource]] = [
        (
            "patient_list_paraphrase",
            "Can you list five patients?",
            "patient_list",
            {},
            5,
            _expected(dataset, "patient_list", None),
        ),
        (
            "condition_cohort_paraphrase",
            "Which patients have type 2 diabetes?",
            "condition_cohort",
            {"condition_code": "44054006"},
            20,
            _expected(dataset, "condition_cohort", None),
        ),
        (
            "latest_lab_paraphrase",
            "Which patients have latest HbA1c above 8% and active Metformin?",
            "latest_lab_medication",
            {"lab_code": "4548-4", "medication_code": "6809", "unit": "%", "threshold": 8},
            20,
            _expected(dataset, "latest_lab_medication", None),
        ),
        (
            "patient_history_paraphrase",
            f"Can you show the history for {patient_id}?",
            "patient_history",
            {"patient_id": patient_id},
            20,
            _history_expected(dataset, patient_id, None),
        ),
    ]
    for name, question, intent, fields, limit, expected in paraphrases:
        cases.append(
            EvaluationCase(
                name,
                {"query": question},
                expected,
                limit,
                {"intent": intent, "limit": limit, "comparison": "gt", **fields},
            )
        )
    return cases


def _lab_history_expected(dataset: Dataset, patient_id: str, lab_code: str | None) -> Resource:
    """Independent raw-FHIR observation history, with every recorded value retained."""
    observations = [
        (identifier, resource)
        for identifier, resource in dataset.resources.items()
        if resource["resourceType"] == "Observation"
        and _patient(resource, dataset) == patient_id
        and resource.get("status") in _FINAL_STATUSES
        and (lab_code is None or _code(resource, "code") == lab_code)
    ]
    observations.sort(key=lambda item: item[0])
    observations.sort(
        key=lambda item: (_timestamp(item[1]) is not None, _timestamp(item[1]) or (0, 0)),
        reverse=True,
    )
    rows = [
        {
            **_patient_row(dataset, patient_id),
            "observation_id": identifier,
            "lab_code": _optional_field(resource, "Observation.code.coding[0].code"),
            "lab_name": _optional_field(resource, "Observation.code.coding[0].display"),
            "lab_status": resource.get("status"),
            "value": _optional_field(resource, "Observation.valueQuantity.value"),
            "unit": _optional_field(resource, "Observation.valueQuantity.unit"),
            "observed_at": resource.get("effectiveDateTime"),
        }
        for identifier, resource in observations
    ]
    return {
        "status": "answered",
        "patient_ids": [patient_id] * len(rows),
        "rows": rows,
        "evidence": [
            _evidence(dataset, patient_id, patient_id),
            *(_evidence(dataset, identifier, patient_id) for identifier, _ in observations),
        ]
        if rows
        else [],
        "row_identity": "observation_id",
    }


def _same_value(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    return bool(actual == expected)


def _validate_response(dataset: Dataset, case: EvaluationCase, payload: Resource) -> list[str]:
    errors = []
    expected = case.expected
    if payload.get("status") != expected["status"]:
        errors.append(f"Expected status {expected['status']!r}, got {payload.get('status')!r}")
    rows, evidence = payload.get("results"), payload.get("evidence")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        errors.append("results must be an array of objects")
        rows = []
    if not isinstance(evidence, list) or not all(isinstance(item, dict) for item in evidence):
        errors.append("evidence must be an array of objects")
        evidence = []
    actual_ids = [row.get("patient_id") for row in rows]
    row_identity = expected.get("row_identity", "patient_id")
    identities = [row.get(row_identity) for row in rows]
    if any(not isinstance(identifier, str) for identifier in actual_ids) or len(
        {
            identifier
            for identifier in identities
            if isinstance(identifier, str) or identifier is None
        }
    ) != len(identities):
        errors.append("Result patient IDs are invalid or duplicated")
    if actual_ids != expected["patient_ids"]:
        errors.append(
            f"Patient IDs differ: expected {expected['patient_ids']!r}, actual {actual_ids!r}"
        )
    if type(payload.get("result_count")) is not int or payload.get("result_count") != len(rows):
        errors.append("result_count does not match the number of result rows")
    for index, (row, required) in enumerate(zip(rows, expected["rows"], strict=False)):
        for key, value in required.items():
            if not _same_value(row.get(key, _MISSING), value):
                errors.append(f"Row {index}: {key} differs from source or expected order")
    expected_evidence = {item["id"]: item for item in expected["evidence"]}
    evidence_ids = [item.get("id") for item in evidence]
    valid_ids = {identifier for identifier in evidence_ids if isinstance(identifier, str)}
    if len(valid_ids) != len(evidence_ids):
        errors.append("Evidence IDs are invalid or duplicated")
    if valid_ids != set(expected_evidence):
        errors.append(
            f"Evidence IDs differ: expected {sorted(expected_evidence)!r}, actual {sorted(valid_ids)!r}"
        )
    for item in evidence:
        identifier = item.get("id")
        required = expected_evidence.get(identifier) if isinstance(identifier, str) else None
        if required is None:
            continue
        for key in ("type", "patient_id", "source_url"):
            if item.get(key) != required[key]:
                errors.append(f"Evidence {identifier}: {key} differs from source")
        if not isinstance(item.get("label"), str) or not item["label"]:
            errors.append(f"Evidence {identifier}: missing label")
        facts = item.get("facts")
        if not isinstance(facts, dict):
            errors.append(f"Evidence {identifier}: facts must be an object")
            continue
        for path, value in required["facts"].items():
            if not _same_value(facts.get(path, _MISSING), value):
                errors.append(f"Evidence {identifier}: {path} missing or differs from source")
        for path, value in facts.items():
            source_value = _field(dataset.resources[identifier], path)
            if source_value is _MISSING or not _same_value(value, source_value):
                errors.append(f"Evidence {identifier}: {path} is not grounded in raw FHIR")
    return errors


def _source_errors(citation: Resource, source: Resource, dataset: Dataset) -> list[str]:
    kind, identifier = citation["id"].split("/", 1)
    if source.get("resourceType") != kind or source.get("id") != identifier:
        return ["FHIR source identity differs from the citation"]
    problems = []
    if kind != "Patient" and _patient(source, dataset) != citation["patient_id"]:
        problems.append("FHIR source patient association differs from the citation")
    return problems + [
        f"FHIR source {path} differs from cited facts"
        for path, value in citation["facts"].items()
        if not _same_value(_field(source, path), value)
    ]


def _page_case(case: EvaluationCase, offset: int) -> EvaluationCase:
    """Select independently expected rows and only their supporting evidence."""
    rows = case.expected["rows"][offset : offset + case.page_limit]
    ids = {
        row[key]
        for row in rows
        for key in ("patient_id", "resource_id", "condition_id", "observation_id", "medication_id")
        if row.get(key)
    }
    expected = {
        **case.expected,
        "rows": rows,
        "patient_ids": [row["patient_id"] for row in rows],
        "evidence": [item for item in case.expected["evidence"] if item["id"] in ids],
    }
    return EvaluationCase(case.name, case.request, expected, case.page_limit, case.expected_plan)


def _pagination_errors(case: EvaluationCase, payload: Resource, offset: int) -> list[str]:
    if case.expected["status"] == "abstained":
        return (
            []
            if payload.get("pagination") is None and payload.get("plan") is None
            else ["Abstention cannot have a plan or pagination"]
        )
    pagination = payload.get("pagination")
    if not isinstance(pagination, dict):
        return ["Missing pagination metadata"]
    more = offset + case.page_limit < len(case.expected["rows"])
    expected = {
        "offset": offset,
        "limit": case.page_limit,
        "has_more": more,
        "next_offset": offset + case.page_limit if more else None,
    }
    errors = [
        f"Pagination {key} differs from independently expected page boundary"
        for key, value in expected.items()
        if type(pagination.get(key)) is not type(value) or pagination.get(key) != value
    ]
    plan = payload.get("plan")
    if (
        not isinstance(plan, dict)
        or type(plan.get("limit")) is not int
        or plan.get("limit") != case.page_limit
    ):
        errors.append("Response plan does not preserve the page limit")
    if (
        not isinstance(plan, dict)
        or case.expected_plan is None
        or set(plan) != set(case.expected_plan)
        or any(not _same_value(plan[key], value) for key, value in case.expected_plan.items())
    ):
        errors.append(
            "Response plan differs from independently expected clinical intent and fields"
        )
    return errors


def _summary_errors(dataset: Dataset, payload: Resource, *, requested: bool) -> list[str]:
    """Validate selections directly against this page and raw NDJSON, independently."""
    claims, metadata = payload.get("claims"), payload.get("summary_metadata")
    if not requested and claims is None and metadata is None:
        return []
    if not isinstance(metadata, dict) or set(metadata) != {
        "requested",
        "status",
        "model",
        "claim_count",
    }:
        return ["Missing or malformed summary metadata"]
    if type(metadata.get("requested")) is not bool or metadata["requested"] != requested:
        return ["Summary requested flag differs from the request"]
    if not isinstance(claims, list) or not all(isinstance(claim, dict) for claim in claims):
        return ["Summary claims must be an array of objects"]
    if type(metadata.get("claim_count")) is not int or metadata["claim_count"] != len(claims):
        return ["Summary claim count differs from selected facts"]
    if not requested or not payload.get("evidence"):
        status = "no_evidence" if requested else "not_requested"
        return (
            []
            if (
                not claims
                and payload.get("summary") is None
                and metadata["status"] == status
                and metadata["model"] is None
            )
            else ["Unexpected summary without requested evidence"]
        )
    if (
        metadata["status"] != "validated"
        or not isinstance(metadata["model"], str)
        or not metadata["model"]
    ):
        return ["Requested summary did not produce validated local-model claims"]
    if not 1 <= len(claims) <= 50:
        return ["Summary must select 1..50 claims"]
    evidence = {
        item["id"]: item
        for item in payload["evidence"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    errors = []
    seen: set[tuple[str, str]] = set()
    rendered = []
    for claim in claims:
        if set(claim) != {"evidence_id", "field", "value"}:
            errors.append("Summary claim contains missing or unchecked fields")
            continue
        identifier, field, value = claim["evidence_id"], claim["field"], claim["value"]
        if not isinstance(identifier, str) or not isinstance(field, str):
            errors.append("Summary claim reference is malformed")
            continue
        if (identifier, field) in seen:
            errors.append("Summary claim duplicates a selected fact")
        seen.add((identifier, field))
        facts = evidence.get(identifier, {}).get("facts", {})
        source = dataset.resources.get(identifier)
        if (
            not isinstance(facts, dict)
            or field not in facts
            or source is None
            or not _same_value(value, facts.get(field, _MISSING))
            or not _same_value(value, _field(source, field))
        ):
            errors.append(
                f"Summary claim {identifier}: {field} is not an exact cited raw-FHIR fact"
            )
            continue
        try:
            rendered.append(
                f"{identifier}: {field} = {json.dumps(value, ensure_ascii=False, allow_nan=False)}."
            )
        except ValueError:
            errors.append("Summary claim value is not a finite JSON value")
    if payload.get("summary") != "\n".join(rendered):
        errors.append("Summary text differs from deterministic rendering of source claims")
    return errors


def run_evaluation(
    dataset: Dataset,
    api_url: str,
    *,
    client: httpx.Client,
    use_summary_model: bool = False,
    case_ids: set[str] | None = None,
) -> Resource:
    """Traverse each case completely, checking every page before following it."""
    cases = []
    sources: dict[str, Resource | str] = {}
    source_checks: dict[str, set[str]] = {}
    selected_cases = build_cases(dataset)
    if case_ids is not None:
        known_ids = {case.name for case in selected_cases}
        if not case_ids or case_ids - known_ids:
            raise ValueError(
                f"Invalid evaluation case selection: {sorted(case_ids - known_ids) if case_ids else 'empty case set'}"
            )
        selected_cases = [case for case in selected_cases if case.name in case_ids]
    for case in selected_cases:
        pages: list[Resource] = []
        payload: Resource = {"results": [], "evidence": [], "result_count": 0}
        all_evidence: dict[str, Resource] = {}
        errors: list[str] = []
        first_plan: Resource | None = None
        try:
            # The oracle bounds traversal; a server cannot cause an infinite page loop.
            for offset in range(0, max(1, len(case.expected["rows"])), case.page_limit):
                request = (
                    case.request
                    if offset == 0
                    else {
                        "query": case.request["query"],
                        "plan": first_plan,
                        "offset": offset,
                    }
                )
                if use_summary_model:
                    request = {**request, "use_summary_model": True}
                response = client.post(f"{api_url.rstrip('/')}/assistant/query", json=request)
                response.raise_for_status()
                decoded = response.json()
                if not isinstance(decoded, dict):
                    raise ValueError("Assistant response must be a JSON object")
                pages.append(decoded)
                errors = _validate_response(dataset, _page_case(case, offset), decoded)
                errors.extend(_pagination_errors(case, decoded, offset))
                errors.extend(_summary_errors(dataset, decoded, requested=use_summary_model))
                if offset == 0:
                    first_plan = decoded.get("plan")
                elif decoded.get("plan") != first_plan:
                    errors.append("Query plan changed between pages")
                if errors:
                    break
                payload["status"] = decoded["status"]
                payload["results"].extend(decoded["results"])
                all_evidence.update((item["id"], item) for item in decoded["evidence"])
                for citation in decoded["evidence"]:
                    identifier = citation["id"]
                    if identifier not in sources:
                        try:
                            source_response = client.get(
                                f"{api_url.rstrip('/')}/resources/{identifier}"
                            )
                            source_response.raise_for_status()
                            decoded_source = source_response.json()
                            if not isinstance(decoded_source, dict):
                                raise ValueError("FHIR source must be a JSON object")
                            sources[identifier] = decoded_source
                        except (httpx.HTTPError, ValueError) as exc:
                            sources[identifier] = f"{type(exc).__name__}: {exc}"
                    source = sources[identifier]
                    problems = (
                        [source]
                        if isinstance(source, str)
                        else _source_errors(citation, source, dataset)
                    )
                    source_checks.setdefault(identifier, set()).update(problems)
                    errors.extend(f"Source {identifier}: {problem}" for problem in problems)
                if errors:
                    break
            payload.update(
                evidence=list(all_evidence.values()),
                result_count=len(payload["results"]),
                plan=first_plan,
            )
            if not errors:
                errors = _validate_response(dataset, case, payload)
        except (httpx.HTTPError, ValueError) as exc:
            errors = [f"{type(exc).__name__}: {exc}"]
        cases.append(
            {
                "name": case.name,
                "request": case.request,
                "expected": case.expected,
                "actual": payload,
                "page_count": len(pages),
                "pages": pages,
                "status": "fail" if errors else "pass",
                "errors": errors,
            }
        )
    return {
        "schema_version": 2,
        "evaluated_at": datetime.now(UTC).isoformat(),
        "input": str(dataset.root),
        "fhir_base_url": dataset.fhir_base_url,
        "api_url": api_url.rstrip("/"),
        "patient_count": len(dataset.patient_ids),
        "summary_model_requested": use_summary_model,
        "selected_case_ids": [case.name for case in selected_cases],
        "status": "pass" if all(case["status"] == "pass" for case in cases) else "fail",
        "cases": cases,
        "source_checks": {
            "total": len(source_checks),
            "passed": sum(not problems for problems in source_checks.values()),
            "failed": sum(bool(problems) for problems in source_checks.values()),
            "resources": [
                {
                    "id": identifier,
                    "status": "fail" if problems else "pass",
                    "errors": sorted(problems),
                }
                for identifier, problems in sorted(source_checks.items())
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, type=Path, help="Dataset root or NDJSON directory"
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8010/api/v1")
    parser.add_argument(
        "--fhir-base-url",
        help="Explicit service base allowed for same-service absolute source references",
    )
    parser.add_argument(
        "--use-summary-model",
        action="store_true",
        help="Also require exact validated local-model fact selections on every nonempty page",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        help="Evaluate only this named case; repeat for explicit bounded coverage (default: all cases)",
    )
    parser.add_argument(
        "--output", required=True, type=Path, help="Machine-readable evaluation report"
    )
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.input, fhir_base_url=args.fhir_base_url)
        with httpx.Client(timeout=30.0) as client:
            report = run_evaluation(
                dataset,
                args.api_url,
                client=client,
                use_summary_model=args.use_summary_model,
                case_ids=set(args.case_id) if args.case_id is not None else None,
            )
    except (OSError, ValueError) as exc:
        report = {
            "schema_version": 2,
            "evaluated_at": datetime.now(UTC).isoformat(),
            "input": str(args.input),
            "api_url": args.api_url.rstrip("/"),
            "status": "fail",
            "cases": [],
            "error": str(exc),
        }
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        print(f"Cannot write evaluation report: {exc}", file=sys.stderr)
        return 1
    source_count = report.get("source_checks", {}).get("total", 0)
    print(
        f"Evaluation {report['status']}: {args.output} ({len(report['cases'])} cases, {source_count} distinct FHIR sources checked)"
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
