"""FHIR Bundle builder utilities."""

from __future__ import annotations

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import Bundle, BundleEntry, BundleEntryRequest


def build_transaction_bundle(
    resources: list[FHIRResource],
    bundle_id: str | None = None,
) -> Bundle:
    """Create a FHIR transaction Bundle from a list of resources.

    Each resource becomes a PUT entry (upsert by resource type/id).
    """
    entries = []
    for resource in resources:
        resource_dict = resource.to_dict()
        entry = BundleEntry(
            fullUrl=f"{resource.resourceType}/{resource.id}",
            resource=resource_dict,
            request=BundleEntryRequest(
                method="PUT",
                url=f"{resource.resourceType}/{resource.id}",
            ),
        )
        entries.append(entry)

    return Bundle(
        id=bundle_id,
        type="transaction",
        entry=entries,
    )
