"""Bounded exact FHIR resource retrieval for evidence inspection."""

from typing import Any

import httpx
from apps.api.app.config import settings
from fastapi import APIRouter, HTTPException, Path

router = APIRouter(prefix="/resources")
SUPPORTED_TYPES = {
    "Patient",
    "Encounter",
    "Condition",
    "Observation",
    "MedicationRequest",
    "Medication",
    "Procedure",
    "AllergyIntolerance",
    "Practitioner",
    "Organization",
    "DiagnosticReport",
    "ServiceRequest",
}


def get_fhir_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=5.0)


@router.get("/{resource_type}/{resource_id}")
async def get_resource(
    resource_type: str, resource_id: str = Path(pattern=r"^[A-Za-z0-9.-]{1,64}$")
) -> dict[str, Any]:
    if resource_type not in SUPPORTED_TYPES:
        raise HTTPException(status_code=404, detail="Unsupported FHIR resource type")
    client = get_fhir_client()
    try:
        response = await client.get(
            f"{settings.hapi_fhir_url.rstrip('/')}/{resource_type}/{resource_id}"
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="FHIR resource not found")
        response.raise_for_status()
        payload = response.json()
        if (
            not isinstance(payload, dict)
            or payload.get("resourceType") != resource_type
            or payload.get("id") != resource_id
        ):
            raise ValueError("Unexpected upstream resource")
        return payload
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail="FHIR source is unavailable or returned an invalid resource"
        ) from exc
    finally:
        await client.aclose()
