"""Deterministic resource ID factory.

All IDs are derived from seed + patient sequence + resource type + sequence
to ensure full reproducibility.
"""

from __future__ import annotations


class IdFactory:
    """Deterministic ID minter for FHIR resources."""

    def __init__(self) -> None:
        self._counters: dict[tuple[str, str], int] = {}

    def patient_id(self, patient_seq: int) -> str:
        """Generate Patient ID: p-000001."""
        return f"p-{patient_seq:06d}"

    def resource_id(self, patient_seq: int, resource_type: str) -> str:
        """Generate a resource ID scoped to a patient.

        Pattern: p-{patient_seq}-{type_prefix}-{seq}
        Example: p-000001-e-0007
        """
        prefix = _TYPE_PREFIXES.get(resource_type, resource_type[0].lower())
        key = (f"p-{patient_seq:06d}", prefix)
        self._counters[key] = self._counters.get(key, 0) + 1
        seq = self._counters[key]
        return f"p-{patient_seq:06d}-{prefix}-{seq:04d}"

    def shared_id(self, resource_type: str, seq: int) -> str:
        """Generate IDs for shared resources (Practitioner, Organization).

        Pattern: {type_prefix}-{seq}
        Example: pract-0042, org-0003
        """
        prefix = _SHARED_PREFIXES.get(resource_type, resource_type[:4].lower())
        return f"{prefix}-{seq:04d}"

    def medication_id(self, code: str) -> str:
        """Generate a stable Medication ID from its code.

        Pattern: med-{code}
        """
        return f"med-{code}"


_TYPE_PREFIXES: dict[str, str] = {
    "Encounter": "e",
    "Condition": "c",
    "Observation": "o",
    "MedicationRequest": "mr",
    "Procedure": "proc",
    "AllergyIntolerance": "ai",
    "DiagnosticReport": "dr",
    "ServiceRequest": "sr",
}

_SHARED_PREFIXES: dict[str, str] = {
    "Practitioner": "pract",
    "Organization": "org",
}
