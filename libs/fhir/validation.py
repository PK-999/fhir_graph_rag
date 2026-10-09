"""Offline validation against a byte-pinned official HL7 FHIR R4 JSON schema.

This is structural validation, not full FHIR conformance. The upstream schema
omits some object types and minimum cardinalities, so separate JSON shape checks
enforce complex-object shape and nonempty arrays. Payloads are never coerced,
normalized, or serialized through the project's partial Pydantic models.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft6Validator, validators

_SCHEMA_DIR = Path(__file__).with_name("schemas")
_SCHEMA_SHA256 = "2230406893b4cf002a4ee1e5e2bbeca22ac5d2d4931b3e9ef7b9594bbc376a01"


@dataclass(frozen=True)
class StructuralIssue:
    """A deterministic validation diagnostic at an original FHIR JSON path."""

    path: str
    message: str
    validator: str


@cache
def load_pinned_schema(path: Path = _SCHEMA_DIR / "fhir-r4.schema.json") -> dict[str, Any]:
    """Load only the exact reviewed upstream schema; never fetch at runtime."""
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != _SCHEMA_SHA256:
        raise ValueError("FHIR R4 schema checksum mismatch")
    schema: dict[str, Any] = json.loads(content)
    return schema


def structural_validation_metadata() -> dict[str, Any]:
    """Describe pinned source, additional shape checks, and conformance limits."""
    manifest: dict[str, Any] = json.loads((_SCHEMA_DIR / "manifest.json").read_text())
    return manifest


def _path(parts: Any) -> str:
    result = ""
    for part in parts:
        if isinstance(part, int):
            result += f"[{part}]"
        else:
            result += f".{part}" if result else str(part)
    return result or "$"


def _finite_number_issues(
    value: object, parts: tuple[str | int, ...] = ()
) -> Iterator[StructuralIssue]:
    """Reject Python decoder extensions that are not valid JSON numbers."""
    if isinstance(value, float) and not math.isfinite(value):
        yield StructuralIssue(
            _path(parts),
            "JSON numbers must be finite; NaN and Infinity are invalid JSON",
            "json_shape",
        )
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _finite_number_issues(child, (*parts, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _finite_number_issues(child, (*parts, index))


@cache
def _validator(resource_type: str) -> Any:
    schema = load_pinned_schema()
    # Select the discriminator's official branch without testing all 146 types
    # for every top-level resource. The upstream definitions stay unmodified.
    return _FHIRValidator(
        {
            "$schema": schema["$schema"],
            "$ref": schema["discriminator"]["mapping"][resource_type],
            "definitions": schema["definitions"],
        }
    )


def _resource_one_of(
    validator: Any, branches: list[dict[str, Any]], instance: object, schema: dict[str, Any]
) -> Iterator[Any]:
    """Dispatch the official disjoint resourceType branches for nested resources.

    Every upstream ResourceList branch fixes resourceType with a distinct const,
    so selecting that branch is equivalent to oneOf and avoids a full scan for
    each bundle entry. Unknown resource types use the original draft-06 behavior.
    """
    if isinstance(instance, dict):
        resource_type = instance.get("resourceType")
        mapping = load_pinned_schema()["discriminator"]["mapping"]
        if isinstance(resource_type, str) and resource_type in mapping:
            selected = {"$ref": mapping[resource_type]}
            if selected in branches:
                yield from validator.descend(
                    instance, selected, schema_path=branches.index(selected)
                )
                return
    yield from Draft6Validator.VALIDATORS["oneOf"](validator, branches, instance, schema)


_FHIRValidator = validators.extend(Draft6Validator, {"oneOf": _resource_one_of})  # type: ignore[no-untyped-call]


def _shape_issues(
    value: object,
    definition: dict[str, Any],
    definitions: dict[str, Any],
    parts: tuple[str | int, ...] = (),
) -> Iterator[StructuralIssue]:
    if "$ref" in definition:
        name = definition["$ref"].removeprefix("#/definitions/")
        if name == "ResourceList" and isinstance(value, dict):
            resource_type = value.get("resourceType")
            if isinstance(resource_type, str) and resource_type in definitions:
                yield from _shape_issues(value, definitions[resource_type], definitions, parts)
            return
        yield from _shape_issues(value, definitions[name], definitions, parts)
        return
    if "properties" in definition:
        if not isinstance(value, dict):
            yield StructuralIssue(
                _path(parts),
                "FHIR complex element must be a JSON object (maximum cardinality 1)",
                "json_shape",
            )
            return
        for key, child in value.items():
            child_definition = definition["properties"].get(key)
            if isinstance(child_definition, dict):
                yield from _shape_issues(child, child_definition, definitions, (*parts, key))
    elif definition.get("type") == "array" and isinstance(value, list):
        if not value:
            yield StructuralIssue(
                _path(parts),
                "FHIR arrays must contain at least one item when present",
                "json_shape",
            )
        for index, child in enumerate(value):
            # FHIR JSON primitive extension arrays use null alignment slots.
            # They are not malformed complex elements (R4 json.html 2.6.2.3).
            if (
                child is None
                and parts
                and isinstance(parts[-1], str)
                and parts[-1].startswith("_")
                and definition["items"].get("$ref") == "#/definitions/Element"
            ):
                continue
            yield from _shape_issues(child, definition["items"], definitions, (*parts, index))


def validate_resource(payload: Any) -> list[StructuralIssue]:
    """Check the original serialized resource without modifying its values."""
    if not isinstance(payload, dict):
        return [StructuralIssue("$", "FHIR resource must be a JSON object", "json_shape")]
    number_issues = list(_finite_number_issues(payload))
    if number_issues:
        return sorted(number_issues, key=lambda issue: issue.path)
    schema = load_pinned_schema()
    resource_type = payload.get("resourceType")
    if (
        not isinstance(resource_type, str)
        or resource_type not in schema["discriminator"]["mapping"]
    ):
        return [
            StructuralIssue(
                "resourceType", "unsupported or missing FHIR R4 resourceType", "discriminator"
            )
        ]
    issues = [
        StructuralIssue(_path(error.absolute_path), error.message, str(error.validator))
        for error in _validator(resource_type).iter_errors(payload)
    ]
    issues.extend(
        _shape_issues(payload, schema["definitions"][resource_type], schema["definitions"])
    )
    return sorted(issues, key=lambda issue: (issue.path, issue.validator, issue.message))
