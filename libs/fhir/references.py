"""Explicit FHIR reference resolution without changing serialized evidence.

The compact index retains identities and bundle aliases, never resource payloads.
Only ``resolved`` results identify graphable top-level resources. Contained,
external, unsupported and unresolved references must not be turned into edges.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

_LOCAL_REFERENCE = re.compile(r"^[A-Z][A-Za-z0-9]+/[A-Za-z0-9.-]{1,64}$")


@dataclass(frozen=True)
class ReferenceOccurrence:
    """One unmodified literal reference and its FHIR JSON path."""

    path: str
    reference: str


@dataclass(frozen=True)
class ReferenceResolution:
    """Resolution outcome; target_key exists only for a local top-level target."""

    reference: str
    status: Literal["resolved", "contained", "unresolved", "external", "unsupported", "ambiguous"]
    target_key: str | None = None
    diagnostic: str | None = None


def iter_references(resource: dict[str, Any]) -> Iterator[ReferenceOccurrence]:
    """Yield every string reference, including empty, URN and fragment values."""
    yield from _walk(resource, "")


def extract_references(resource: dict[str, Any]) -> Iterator[str]:
    """Compatibility iterator over the original literal reference strings."""
    for occurrence in iter_references(resource):
        yield occurrence.reference


def _walk(obj: object, path: str) -> Iterator[ReferenceOccurrence]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else key
            if key == "reference" and isinstance(value, str):
                yield ReferenceOccurrence(child_path, value)
            yield from _walk(value, child_path)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            yield from _walk(item, f"{path}[{index}]")


def resource_key(resource: dict[str, Any]) -> str | None:
    """Return a valid resourceType/id identity, without coercion."""
    resource_type, resource_id = resource.get("resourceType"), resource.get("id")
    if isinstance(resource_type, str) and isinstance(resource_id, str):
        key = f"{resource_type}/{resource_id}"
        if _LOCAL_REFERENCE.fullmatch(key):
            return key
    return None


class ReferenceIndex:
    """Incremental identity index for a complete first pass before resolution.

    ``bundle_scope`` separates fullUrl aliases between bundles. An absolute
    reference becomes local only by an exact alias or an explicitly configured
    service base. A relative bundle reference uses its source entry's fullUrl
    base when one is available. Version-specific references are diagnosed rather
    than silently mapped to the current resource.
    """

    def __init__(
        self,
        resources: Iterable[dict[str, Any]] = (),
        *,
        service_base_url: str | None = None,
    ) -> None:
        self.known_ids: set[str] = set()
        self.service_base_url = service_base_url.rstrip("/") if service_base_url else None
        if self.service_base_url:
            parsed = urlsplit(self.service_base_url)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("service_base_url must be an absolute HTTP(S) base URL")
        self._aliases: dict[tuple[str | None, str], set[str]] = defaultdict(set)
        self._source_bases: dict[tuple[str | None, str], set[str]] = defaultdict(set)
        self._unknown_source_bases: set[tuple[str | None, str]] = set()
        for resource in resources:
            self.add(resource)

    def add(
        self,
        resource: dict[str, Any],
        *,
        full_url: str | None = None,
        bundle_scope: str | None = None,
    ) -> str:
        """Index one valid identity, optionally with its original bundle fullUrl."""
        key = resource_key(resource)
        if key is None:
            raise ValueError("resource is missing a valid resourceType/id identity")
        self.known_ids.add(key)
        if full_url is not None:
            if not isinstance(full_url, str) or not full_url:
                raise ValueError("bundle fullUrl must be a nonempty string")
            self._aliases[(bundle_scope, full_url)].add(key)
            parsed = urlsplit(full_url)
            if parsed.scheme in {"http", "https"} and full_url.endswith(f"/{key}"):
                self._source_bases[(bundle_scope, key)].add(full_url[: -(len(key) + 1)])
            elif parsed.scheme in {"http", "https"}:
                self._unknown_source_bases.add((bundle_scope, key))
        return key

    def add_bundle(self, bundle: dict[str, Any], *, bundle_scope: str | None = None) -> None:
        """Index resource entries and aliases from a previously validated bundle."""
        for entry in bundle.get("entry", []):
            if isinstance(entry, dict) and isinstance(entry.get("resource"), dict):
                self.add(
                    entry["resource"], full_url=entry.get("fullUrl"), bundle_scope=bundle_scope
                )

    def _target(self, reference: str, targets: set[str]) -> ReferenceResolution:
        if len(targets) > 1:
            return ReferenceResolution(
                reference, "ambiguous", diagnostic="fullUrl alias has multiple targets"
            )
        if targets:
            return ReferenceResolution(reference, "resolved", target_key=next(iter(targets)))
        return ReferenceResolution(
            reference, "unresolved", diagnostic="target is absent from the indexed dataset"
        )

    def resolve(
        self,
        reference: str,
        source_resource: dict[str, Any],
        *,
        bundle_scope: str | None = None,
        path: str = "",
    ) -> ReferenceResolution:
        """Resolve a literal reference in its enclosing top-level resource context."""
        if not reference or reference.strip() != reference:
            return ReferenceResolution(
                reference, "unsupported", diagnostic="empty or whitespace-padded reference"
            )
        if reference.startswith("#"):
            if reference == "#":
                status: Literal["contained", "unsupported"] = (
                    "contained" if path.startswith("contained[") else "unsupported"
                )
                return ReferenceResolution(
                    reference, status, diagnostic="contained reference to enclosing resource"
                )
            contained = source_resource.get("contained", [])
            contained_targets = (
                [
                    item
                    for item in contained
                    if isinstance(item, dict) and item.get("id") == reference[1:]
                ]
                if isinstance(contained, list)
                else []
            )
            if len(contained_targets) > 1:
                return ReferenceResolution(
                    reference, "ambiguous", diagnostic="duplicate contained id"
                )
            if contained_targets:
                return ReferenceResolution(reference, "contained")
            return ReferenceResolution(
                reference, "unresolved", diagnostic="contained id is absent from enclosing resource"
            )
        try:
            parsed = urlsplit(reference)
        except ValueError:
            return ReferenceResolution(
                reference, "unsupported", diagnostic="malformed absolute reference URL"
            )
        if "/_history/" in parsed.path or parsed.query or parsed.fragment:
            return ReferenceResolution(
                reference,
                "unsupported",
                diagnostic="version, query or fragment reference is not supported",
            )
        aliases = self._aliases.get((bundle_scope, reference), set())
        if parsed.scheme:
            if aliases:
                return self._target(reference, aliases)
            if parsed.scheme == "urn":
                return ReferenceResolution(
                    reference,
                    "unresolved",
                    diagnostic="URN has no fullUrl alias in this bundle scope",
                )
            if self.service_base_url and reference.startswith(f"{self.service_base_url}/"):
                key = reference[len(self.service_base_url) + 1 :]
                if _LOCAL_REFERENCE.fullmatch(key):
                    return self._target(reference, {key} if key in self.known_ids else set())
                return ReferenceResolution(
                    reference, "unsupported", diagnostic="unsupported same-service reference path"
                )
            return ReferenceResolution(
                reference,
                "external",
                diagnostic="absolute reference is outside the indexed service and bundle aliases",
            )
        if not _LOCAL_REFERENCE.fullmatch(reference):
            return ReferenceResolution(
                reference, "unsupported", diagnostic="unsupported relative reference syntax"
            )
        source_key = resource_key(source_resource)
        if (bundle_scope, source_key or "") in self._unknown_source_bases:
            return ReferenceResolution(
                reference,
                "unsupported",
                diagnostic="cannot determine a relative service base from the source fullUrl",
            )
        bases = self._source_bases.get((bundle_scope, source_key or ""), set())
        if len(bases) > 1:
            return ReferenceResolution(
                reference, "ambiguous", diagnostic="source fullUrl has multiple service bases"
            )
        if bases:
            base = next(iter(bases))
            targets = self._aliases.get((bundle_scope, f"{base}/{reference}"), set())
            if targets:
                return self._target(reference, targets)
            if base != self.service_base_url:
                return ReferenceResolution(
                    reference,
                    "unresolved",
                    diagnostic="relative reference is absent from the source fullUrl service base",
                )
        if aliases:
            return self._target(reference, aliases)
        return self._target(reference, {reference} if reference in self.known_ids else set())


def validate_references(
    resource: dict[str, Any], known_ids: set[str] | ReferenceIndex
) -> list[str]:
    """Compatibility result listing literal references that cannot resolve locally."""
    if isinstance(known_ids, set):
        index = ReferenceIndex()
        index.known_ids.update(known_ids)
    else:
        index = known_ids
    return [
        occurrence.reference
        for occurrence in iter_references(resource)
        if index.resolve(occurrence.reference, resource, path=occurrence.path).status
        not in {"resolved", "contained"}
    ]
