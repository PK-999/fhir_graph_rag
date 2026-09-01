"""FHIR reference extractor and validator.

Walks any FHIR resource dict and yields all reference strings.
"""

from __future__ import annotations

from collections.abc import Iterator


def extract_references(resource: dict) -> Iterator[str]:
    """Recursively extract all FHIR reference strings from a resource dict.

    Yields reference strings like 'Patient/p-000001'.
    """
    yield from _walk(resource)


def _walk(obj: object) -> Iterator[str]:
    """Recursively walk a dict/list and yield reference strings."""
    if isinstance(obj, dict):
        # If this dict has a "reference" key, yield its value
        ref = obj.get("reference")
        if isinstance(ref, str) and "/" in ref:
            yield ref
        # Recurse into all values
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk(item)


def validate_references(
    resource: dict,
    known_ids: set[str],
) -> list[str]:
    """Check that all references in a resource resolve to known IDs.

    Returns a list of unresolved reference strings.
    """
    unresolved = []
    for ref in extract_references(resource):
        if ref not in known_ids:
            unresolved.append(ref)
    return unresolved
