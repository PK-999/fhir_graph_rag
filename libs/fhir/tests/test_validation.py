"""Independent invalid-payload tests for pinned R4 structural validation."""

from __future__ import annotations

import copy
import json

import pytest


@pytest.mark.parametrize(
    ("payload", "path"),
    [
        ({"resourceType": "Patient", "id": "p1", "active": "true"}, "active"),
        ({"resourceType": "Patient", "id": "p1", "gender": "invalid"}, "gender"),
        ({"resourceType": "Patient", "id": "p1", "name": {"family": "Smith"}}, "name"),
        ({"resourceType": "Observation", "id": "o1", "status": "final"}, "$"),
        (
            {"resourceType": "Encounter", "id": "e1", "class": [{"code": "AMB"}]},
            "class",
        ),
        ({"resourceType": "Patient", "id": "p1", "name": []}, "name"),
        ({"resourceType": "Patient", "id": "p1", "unknownField": "value"}, "$"),
        ({"resourceType": "NotAResource", "id": "p1"}, "resourceType"),
    ],
)
def test_structural_validation_rejects_invalid_serialized_fields(
    payload: dict[str, object], path: str
) -> None:
    from libs.fhir.validation import validate_resource

    issues = validate_resource(payload)

    assert issues
    assert any(issue.path == path for issue in issues)


def test_validation_preserves_unknown_valid_extensions_and_exact_source_values() -> None:
    from libs.fhir.validation import validate_resource

    payload: dict[str, object] = {
        "resourceType": "Observation",
        "id": "o1",
        "status": "final",
        "code": {"text": "example"},
        "valueQuantity": {"value": 1.25, "unit": "mg"},
        "extension": [{"url": "https://example.org/source", "valueString": "unchanged"}],
        "subject": {"reference": "https://outside.example/fhir/Patient/p1"},
    }
    original = copy.deepcopy(payload)

    assert validate_resource(payload) == []
    assert payload == original


def test_schema_does_not_claim_unimplemented_terminology_or_choice_invariants() -> None:
    from libs.fhir.validation import structural_validation_metadata, validate_resource

    payload = {
        "resourceType": "Observation",
        "status": "final",
        "code": {"coding": [{"system": "https://example.org/unknown", "code": "anything"}]},
        "valueString": "one choice",
        "valueBoolean": True,
    }

    assert validate_resource(payload) == []
    metadata = structural_validation_metadata()
    assert metadata["validation_scope"] == "FHIR R4 structural JSON schema and JSON shape checks"
    assert "terminology" in " ".join(metadata["limitations"])


def test_schema_integrity_failure_is_fail_closed(tmp_path: object) -> None:
    from pathlib import Path

    from libs.fhir.validation import load_pinned_schema

    path = Path(str(tmp_path)) / "schema.json"
    path.write_text('{"definitions": {}}')

    with pytest.raises(ValueError, match="checksum"):
        load_pinned_schema(path)


def test_nested_bundle_errors_name_the_field_without_dumping_source_payload() -> None:
    from libs.fhir.validation import validate_resource

    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": {"resourceType": "Patient", "id": "p1", "active": "bad"}}],
    }

    issues = validate_resource(bundle)

    assert any(issue.path == "entry[0].resource.active" for issue in issues)
    assert all("resourceType" not in issue.message for issue in issues)


def test_shape_checks_allow_documented_primitive_extension_array_null_placeholders() -> None:
    from libs.fhir.validation import validate_resource

    patient = {
        "resourceType": "Patient",
        "name": [
            {
                "given": ["Ada", "Beth"],
                "_given": [
                    None,
                    {"extension": [{"url": "https://example.org/ext", "valueString": "source"}]},
                ],
            }
        ],
    }

    assert validate_resource(patient) == []


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("nested_extension", [False, True])
def test_structural_validation_rejects_nonfinite_numbers_without_changing_source(
    value: float, nested_extension: bool
) -> None:
    from libs.fhir.validation import validate_resource

    payload: dict[str, object] = {
        "resourceType": "Observation",
        "id": "o1",
        "status": "final",
        "code": {"text": "example"},
    }
    if nested_extension:
        payload["extension"] = [
            {
                "url": "https://example.org/outer",
                "extension": [{"url": "https://example.org/inner", "valueDecimal": value}],
            }
        ]
        expected_path = "extension[0].extension[0].valueDecimal"
    else:
        payload["valueQuantity"] = {"value": value, "unit": "mg"}
        expected_path = "valueQuantity.value"
    original = json.dumps(payload, sort_keys=True)

    issues = validate_resource(payload)

    assert any(
        issue.path == expected_path
        and issue.validator == "json_shape"
        and "finite" in issue.message
        for issue in issues
    )
    assert json.dumps(payload, sort_keys=True) == original


@pytest.mark.parametrize("value", [0.0, 5e-324, 1.7976931348623157e308, -1.7976931348623157e308])
def test_structural_validation_accepts_finite_json_number_bounds(value: float) -> None:
    from libs.fhir.validation import validate_resource

    payload = {
        "resourceType": "Observation",
        "status": "final",
        "code": {"text": "example"},
        "valueQuantity": {"value": value, "unit": "mg"},
    }

    assert validate_resource(payload) == []


def test_nonfinite_number_in_bundle_resource_reports_its_original_nested_path() -> None:
    from libs.fhir.validation import validate_resource

    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "code": {"text": "example"},
                    "valueQuantity": {"value": float("inf")},
                }
            }
        ],
    }

    issues = validate_resource(bundle)

    assert any(issue.path == "entry[0].resource.valueQuantity.value" for issue in issues)
