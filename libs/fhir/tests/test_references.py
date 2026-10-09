"""Reference resolution must never invent local identities or rewrite evidence."""

from __future__ import annotations

import copy

import pytest

from libs.fhir import references


def test_reference_iterator_includes_urn_contained_and_invalid_strings_with_paths() -> None:
    resource = {
        "subject": {"reference": "urn:uuid:patient"},
        "performer": [{"reference": "#doctor"}, {"reference": ""}],
    }

    assert list(references.extract_references(resource)) == ["urn:uuid:patient", "#doctor", ""]
    occurrences = list(references.iter_references(resource))
    assert [(item.path, item.reference) for item in occurrences] == [
        ("subject.reference", "urn:uuid:patient"),
        ("performer[0].reference", "#doctor"),
        ("performer[1].reference", ""),
    ]


@pytest.mark.parametrize(
    ("reference", "status", "target_key"),
    [
        ("Patient/p1", "resolved", "Patient/p1"),
        ("https://local.example/fhir/Patient/p1", "resolved", "Patient/p1"),
        ("https://other.example/fhir/Patient/p1", "external", None),
        ("https://local.example/fhir-extra/Patient/p1", "external", None),
        ("Patient/missing", "unresolved", None),
        ("urn:uuid:unknown", "unresolved", None),
        ("Patient/p1/_history/3", "unsupported", None),
        ("Patient/p1?query=1", "unsupported", None),
        ("", "unsupported", None),
    ],
)
def test_reference_resolution_only_maps_explicit_local_targets(
    reference: str, status: str, target_key: str | None
) -> None:
    index = references.ReferenceIndex(service_base_url="https://local.example/fhir/")
    index.add({"resourceType": "Patient", "id": "p1"})
    source = {"resourceType": "Observation", "id": "o1", "subject": {"reference": reference}}
    original = copy.deepcopy(source)

    result = index.resolve(reference, source)

    assert result.status == status
    assert result.target_key == target_key
    assert source == original


def test_bundle_aliases_are_scoped_and_unknown_external_references_stay_external() -> None:
    index = references.ReferenceIndex()
    patient = {"resourceType": "Patient", "id": "p1"}
    source = {"resourceType": "Observation", "id": "o1"}
    index.add(patient, full_url="urn:uuid:patient", bundle_scope="a")
    index.add(source, full_url="https://bundle.example/fhir/Observation/o1", bundle_scope="a")
    index.add(patient, full_url="https://bundle.example/fhir/Patient/p1", bundle_scope="a")

    assert index.resolve("urn:uuid:patient", source, bundle_scope="a").target_key == "Patient/p1"
    assert index.resolve("urn:uuid:patient", source, bundle_scope="b").status == "unresolved"
    assert index.resolve("Patient/p1", source, bundle_scope="a").target_key == "Patient/p1"
    assert index.resolve("https://elsewhere/fhir/Patient/p1", source).status == "external"


def test_bundle_relative_reference_uses_source_fullurl_base_before_local_ids() -> None:
    index = references.ReferenceIndex([{"resourceType": "Patient", "id": "p1"}])
    source = {"resourceType": "Observation", "id": "o1"}
    index.add(source, full_url="https://external.example/fhir/Observation/o1", bundle_scope="a")

    assert index.resolve("Patient/p1", source, bundle_scope="a").status == "unresolved"


def test_contained_references_use_the_enclosing_resource_and_have_no_graphable_key() -> None:
    source = {
        "resourceType": "Observation",
        "id": "o1",
        "contained": [{"resourceType": "Practitioner", "id": "doctor"}],
        "performer": [{"reference": "#doctor"}],
    }
    index = references.ReferenceIndex([source])

    result = index.resolve("#doctor", source)

    assert result.status == "contained"
    assert result.target_key is None
    assert index.resolve("#missing", source).status == "unresolved"
    assert index.resolve("#", source, path="contained[0].subject.reference").status == "contained"
    assert index.resolve("#", source, path="subject.reference").status == "unsupported"


def test_alias_collisions_are_ambiguous_rather_than_last_write_wins() -> None:
    index = references.ReferenceIndex()
    index.add({"resourceType": "Patient", "id": "p1"}, full_url="urn:uuid:same")
    index.add({"resourceType": "Patient", "id": "p2"}, full_url="urn:uuid:same")

    assert (
        index.resolve("urn:uuid:same", {"resourceType": "Observation", "id": "o1"}).status
        == "ambiguous"
    )


def test_malformed_absolute_reference_is_diagnosed_without_crashing_validation() -> None:
    index = references.ReferenceIndex()

    result = index.resolve(
        "https://[invalid/Patient/p1", {"resourceType": "Observation", "id": "o1"}
    )

    assert result.status == "unsupported"
    assert result.target_key is None


def test_bundle_relative_alias_does_not_override_the_source_fullurl_service_base() -> None:
    index = references.ReferenceIndex()
    source = {"resourceType": "Observation", "id": "o1"}
    index.add(source, full_url="https://external.example/fhir/Observation/o1", bundle_scope="a")
    index.add({"resourceType": "Patient", "id": "p1"}, full_url="Patient/p1", bundle_scope="a")

    assert index.resolve("Patient/p1", source, bundle_scope="a").status == "unresolved"


def test_nonrest_source_fullurl_cannot_invent_a_relative_service_base() -> None:
    index = references.ReferenceIndex([{"resourceType": "Patient", "id": "p1"}])
    source = {"resourceType": "Observation", "id": "o1"}
    index.add(source, full_url="https://external.example/custom-observation", bundle_scope="a")

    assert index.resolve("Patient/p1", source, bundle_scope="a").status == "unsupported"
