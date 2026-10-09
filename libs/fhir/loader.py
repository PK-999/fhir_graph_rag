"""HAPI FHIR loader and client."""

import logging
from typing import Any, cast

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class FHIRLoaderError(Exception):
    """Base exception for FHIR loader errors."""

    pass


class FHIRLoader:
    """Client for uploading transaction Bundles to a FHIR server."""

    def __init__(self, base_url: str = "http://localhost:8080/fhir") -> None:
        self.base_url = base_url.rstrip("/")
        # High timeout because large transaction bundles take time to process
        self.client = httpx.AsyncClient(timeout=60.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def upload_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        """POST a transaction bundle to the FHIR server.

        Retries on connection errors and 5xx/429 status codes.
        """
        response = await self.client.post(
            self.base_url,
            json=bundle,
            headers={"Content-Type": "application/fhir+json"},
        )

        # Raise for 4xx/5xx (triggers retry for 5xx/429 handled by tenacity if we subclassed it,
        # but httpx.HTTPStatusError covers them. We want to fail fast on 4xx except 429)
        if response.status_code >= 400:
            if response.status_code < 500 and response.status_code != 429:
                logger.error(f"Client error {response.status_code}: {response.text}")
                # Don't retry 400 Bad Request (usually validation error)
                raise FHIRLoaderError(
                    f"FHIR server rejected bundle: {response.status_code} {response.text}"
                )
            response.raise_for_status()

        data = response.json()
        entries = data.get("entry") if isinstance(data, dict) else None
        expected = bundle.get("entry", [])
        if (
            response.status_code != 200
            or not isinstance(data, dict)
            or data.get("resourceType") != "Bundle"
            or data.get("type") != "transaction-response"
            or not isinstance(entries, list)
            or len(entries) != len(expected)
        ):
            raise FHIRLoaderError("FHIR transaction response did not confirm every input entry")
        for entry in entries:
            status = entry.get("response", {}).get("status", "") if isinstance(entry, dict) else ""
            if (
                not isinstance(status, str)
                or not status.split()
                or not status.split()[0].isdigit()
                or int(status.split()[0]) not in {200, 201, 204}
            ):
                raise FHIRLoaderError(
                    f"FHIR transaction entry failed or was unconfirmed: {status!r}"
                )
        return cast("dict[str, Any]", data)

    async def get_resource_count(self, resource_type: str) -> int:
        """Get the total count of a resource type using _summary=count."""
        response = await self.client.get(
            f"{self.base_url}/{resource_type}",
            params={"_summary": "count"},
        )
        response.raise_for_status()
        data = cast("dict[str, Any]", response.json())
        return int(data.get("total", 0))
