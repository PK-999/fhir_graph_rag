"""Eight independent quality rules for serialized synthetic FHIR data."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from contextlib import suppress
from datetime import date, datetime
from typing import Any

from libs.fhir.references import ReferenceIndex, iter_references, resource_key
from libs.fhir.validation import structural_validation_metadata, validate_resource
from libs.quality.models import DatasetSnapshot, RuleResult

SCENARIO_PREREQUISITES = {
    "6809": "44054006",  # Metformin requires Type 2 diabetes.
    "29046": "38341003",  # Lisinopril requires hypertension.
}


def _result(
    name: str,
    checked: int,
    failures: list[str],
    details: dict[str, Any] | None = None,
) -> RuleResult:
    return RuleResult(
        name=name,
        status="fail" if failures else "pass",
        checked=checked,
        failures=sorted(failures),
        details=details or {},
    )


def _full_id(payload: dict[str, Any]) -> str | None:
    resource_type = payload.get("resourceType")
    resource_id = payload.get("id")
    if isinstance(resource_type, str) and isinstance(resource_id, str):
        return f"{resource_type}/{resource_id}"
    return None


def _first_code(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    coding = value.get("coding")
    if not isinstance(coding, list) or not coding or not isinstance(coding[0], dict):
        return None
    code = coding[0].get("code")
    return code if isinstance(code, str) else None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def schema_validation(snapshot: DatasetSnapshot) -> RuleResult:
    failures = list(snapshot.read_failures)
    expected_files = snapshot.manifest.get("files")
    if not isinstance(expected_files, dict):
        failures.append("dataset manifest is missing file checksums")
    else:
        actual_files = sorted(
            path
            for directory_name in ("bundles", "ndjson")
            for path in (snapshot.output_dir / directory_name).glob("**/*")
            if path.is_file()
        )
        actual_relative_paths = {
            path.relative_to(snapshot.output_dir).as_posix() for path in actual_files
        }
        expected_relative_paths = set(expected_files)
        for relative_path in sorted(expected_relative_paths - actual_relative_paths):
            failures.append(f"{relative_path}: file is missing")
        for relative_path in sorted(actual_relative_paths - expected_relative_paths):
            failures.append(f"{relative_path}: file is absent from manifest")
        dataset_digest = hashlib.sha256()
        for path in actual_files:
            relative_path = path.relative_to(snapshot.output_dir).as_posix()
            content = path.read_bytes()
            actual_hash = hashlib.sha256(content).hexdigest()
            if expected_files.get(relative_path) != actual_hash:
                failures.append(f"{relative_path}: checksum mismatch")
            dataset_digest.update(relative_path.encode())
            dataset_digest.update(b"\0")
            dataset_digest.update(content)
            dataset_digest.update(b"\0")
        if snapshot.manifest.get("dataset_hash") != dataset_digest.hexdigest():
            failures.append("dataset hash mismatch")
    for record in snapshot.records:
        # FHIR permits resources without ids in some contexts; this dataset's
        # persistent PUT/upsert contract independently requires a stable id.
        if resource_key(record.payload) is None:
            failures.append(
                f"{record.source}: missing or invalid resourceType/id for dataset ingestion"
            )
        for issue in validate_resource(record.payload):
            failures.append(f"{record.source}: {issue.path}: {issue.message} [{issue.validator}]")
    for record in snapshot.bundle_records:
        for issue in validate_resource(record.payload):
            failures.append(f"{record.source}: {issue.path}: {issue.message} [{issue.validator}]")
    details = {**structural_validation_metadata(), "bundles_checked": len(snapshot.bundle_records)}
    return _result("schema_validation", len(snapshot.records), failures, details)


def duplicate_ids(snapshot: DatasetSnapshot) -> RuleResult:
    ids = [full_id for record in snapshot.records if (full_id := _full_id(record.payload))]
    failures = [full_id for full_id, count in Counter(ids).items() if count > 1]
    return _result("duplicate_ids", len(ids), failures)


def reference_resolution(snapshot: DatasetSnapshot) -> RuleResult:
    index = ReferenceIndex(service_base_url=snapshot.service_base_url)
    for record in snapshot.records:
        if resource_key(record.payload):
            index.add(record.payload)
    resource_scopes: dict[str, set[str]] = defaultdict(set)
    bundle_resources: list[tuple[dict[str, Any], str, str]] = []
    for record in snapshot.bundle_records:
        entries = record.payload.get("entry", [])
        if not isinstance(entries, list):
            continue
        for entry_number, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict):
                continue
            resource = entry["resource"]
            key = resource_key(resource)
            if key is None:
                continue
            full_url = entry.get("fullUrl")
            if full_url is not None and (not isinstance(full_url, str) or not full_url):
                continue  # Structural diagnostics identify invalid fullUrl values.
            index.add(resource, full_url=full_url, bundle_scope=record.source)
            resource_scopes[key].add(record.source)
            source = f"{record.source}.entry[{entry_number}].resource"
            bundle_resources.append((resource, record.source, source))
    failures: list[str] = []
    statuses: Counter[str] = Counter()
    checked = 0
    for record in snapshot.records:
        source = _full_id(record.payload) or record.source
        scopes = resource_scopes.get(resource_key(record.payload) or "", set())
        scope = next(iter(scopes)) if len(scopes) == 1 else None
        for occurrence in iter_references(record.payload):
            checked += 1
            result = index.resolve(
                occurrence.reference, record.payload, bundle_scope=scope, path=occurrence.path
            )
            statuses[result.status] += 1
            if result.status not in {"resolved", "contained"}:
                failures.append(
                    f"{source}.{occurrence.path} -> {occurrence.reference} [{result.status}]: {result.diagnostic}"
                )
    bundle_reference_count = 0
    for resource, scope, source in bundle_resources:
        for occurrence in iter_references(resource):
            bundle_reference_count += 1
            result = index.resolve(
                occurrence.reference, resource, bundle_scope=scope, path=occurrence.path
            )
            if result.status not in {"resolved", "contained"}:
                failures.append(
                    f"{source}.{occurrence.path} -> {occurrence.reference} [{result.status}]: {result.diagnostic}"
                )
    return _result(
        "reference_resolution",
        checked,
        failures,
        {
            "statuses": dict(sorted(statuses.items())),
            "bundle_references_checked": bundle_reference_count,
            "service_base_url": snapshot.service_base_url,
        },
    )


def temporal_consistency(snapshot: DatasetSnapshot) -> RuleResult:
    birth_dates: dict[str, date] = {}
    for record in snapshot.records:
        if record.payload.get("resourceType") != "Patient":
            continue
        full_id = _full_id(record.payload)
        birth_date = record.payload.get("birthDate")
        if full_id and isinstance(birth_date, str):
            with suppress(ValueError):
                birth_dates[full_id] = date.fromisoformat(birth_date)

    failures: list[str] = []
    checked = 0
    for record in snapshot.records:
        if record.payload.get("resourceType") != "Encounter":
            continue
        checked += 1
        full_id = _full_id(record.payload) or record.source
        period = record.payload.get("period")
        subject = record.payload.get("subject")
        if not isinstance(period, dict):
            failures.append(f"{full_id}: missing period")
            continue
        start = _parse_datetime(period.get("start"))
        end = _parse_datetime(period.get("end"))
        if start is None or end is None:
            failures.append(f"{full_id}: invalid period")
            continue
        if end < start:
            failures.append(f"{full_id}: end precedes start")
        patient_ref = subject.get("reference") if isinstance(subject, dict) else None
        if (
            isinstance(patient_ref, str)
            and patient_ref in birth_dates
            and start.date() < birth_dates[patient_ref]
        ):
            failures.append(f"{full_id}: starts before patient birth")
    return _result("temporal_consistency", checked, failures)


def _iter_codings(value: object, path: str = "") -> Iterator[tuple[str, object]]:
    if isinstance(value, dict):
        coding = value.get("coding")
        if isinstance(coding, list):
            for index, item in enumerate(coding):
                yield f"{path}.coding[{index}]", item
        for key, child in value.items():
            yield from _iter_codings(child, f"{path}.{key}" if path else key)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_codings(child, f"{path}[{index}]")


def coded_values(snapshot: DatasetSnapshot) -> RuleResult:
    failures: list[str] = []
    checked = 0
    for record in snapshot.records:
        full_id = _full_id(record.payload) or record.source
        for path, coding in _iter_codings(record.payload):
            checked += 1
            if not isinstance(coding, dict):
                failures.append(f"{full_id} {path}: coding must be an object")
                continue
            missing = [field for field in ("system", "code") if not coding.get(field)]
            if missing:
                failures.append(f"{full_id} {path}: missing {', '.join(missing)}")
    return _result("coded_values", checked, failures)


def encounter_count(snapshot: DatasetSnapshot) -> RuleResult:
    generation = snapshot.manifest.get("generation", {})
    encounters = generation.get("encounters", {}) if isinstance(generation, dict) else {}
    minimum = encounters.get("min_per_patient") if isinstance(encounters, dict) else None
    maximum = encounters.get("max_per_patient") if isinstance(encounters, dict) else None
    failures: list[str] = []
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        failures.append("dataset manifest is missing encounter bounds")
    else:
        for patient_id, count in sorted(snapshot.bundle_encounter_counts.items()):
            if not minimum <= count <= maximum:
                failures.append(f"{patient_id} has {count} encounters")
    details = {
        "minimum": min(snapshot.bundle_encounter_counts.values(), default=0),
        "maximum": max(snapshot.bundle_encounter_counts.values(), default=0),
        "mean": round(
            sum(snapshot.bundle_encounter_counts.values())
            / max(len(snapshot.bundle_encounter_counts), 1),
            1,
        ),
        "configured_minimum": minimum,
        "configured_maximum": maximum,
    }
    return _result(
        "encounter_count",
        len(snapshot.bundle_encounter_counts),
        failures,
        details,
    )


def clinical_scenario_consistency(snapshot: DatasetSnapshot) -> RuleResult:
    conditions: dict[str, set[str]] = defaultdict(set)
    medication_records: list[dict[str, Any]] = []
    for record in snapshot.records:
        resource_type = record.payload.get("resourceType")
        subject = record.payload.get("subject")
        patient_ref = subject.get("reference") if isinstance(subject, dict) else None
        if not isinstance(patient_ref, str):
            continue
        if resource_type == "Condition":
            if condition_code := _first_code(record.payload.get("code")):
                conditions[patient_ref].add(condition_code)
        elif resource_type == "MedicationRequest":
            medication_records.append(record.payload)

    failures: list[str] = []
    checked = 0
    for medication in medication_records:
        medication_code = _first_code(medication.get("medicationCodeableConcept"))
        required_condition = SCENARIO_PREREQUISITES.get(medication_code or "")
        if required_condition is None:
            continue
        checked += 1
        subject = medication.get("subject")
        patient_ref = subject.get("reference") if isinstance(subject, dict) else None
        if not isinstance(patient_ref, str) or required_condition not in conditions[patient_ref]:
            full_id = _full_id(medication) or "MedicationRequest/<missing-id>"
            failures.append(
                f"{full_id} requires Condition {required_condition} for {patient_ref or '<missing-subject>'}"
            )
    return _result("clinical_scenario_consistency", checked, failures)


def aggregate_distribution(snapshot: DatasetSnapshot) -> RuleResult:
    resource_counts = Counter(
        resource_type
        for record in snapshot.records
        if isinstance((resource_type := record.payload.get("resourceType")), str)
    )
    gender_counts = Counter(
        gender
        for record in snapshot.records
        if record.payload.get("resourceType") == "Patient"
        and isinstance((gender := record.payload.get("gender")), str)
    )
    failures = [] if resource_counts.get("Patient", 0) > 0 else ["dataset has no Patient resources"]
    details = {
        "patient_count": resource_counts.get("Patient", 0),
        "total_resources": sum(resource_counts.values()),
        "resource_counts": dict(sorted(resource_counts.items())),
        "gender_counts": dict(sorted(gender_counts.items())),
    }
    return _result("aggregate_distribution", len(snapshot.records), failures, details)


RULES: tuple[Callable[[DatasetSnapshot], RuleResult], ...] = (
    schema_validation,
    duplicate_ids,
    reference_resolution,
    temporal_consistency,
    coded_values,
    encounter_count,
    clinical_scenario_consistency,
    aggregate_distribution,
)
