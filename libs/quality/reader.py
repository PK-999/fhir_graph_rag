"""Load generated Bundles, NDJSON, and manifest without trusting generator state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from libs.quality.models import DatasetSnapshot, ResourceRecord


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("expected a JSON object")
    return payload


def load_dataset(output_dir: Path, *, service_base_url: str | None = None) -> DatasetSnapshot:
    """Load all validation inputs and preserve malformed inputs as failures."""
    records: list[ResourceRecord] = []
    bundle_records: list[ResourceRecord] = []
    read_failures: list[str] = []
    manifest: dict[str, Any] = {}
    bundle_encounter_counts: dict[str, int] = {}

    manifest_path = output_dir / "dataset_manifest.json"
    try:
        manifest = _read_json_object(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        read_failures.append(f"dataset_manifest.json: {exc}")

    ndjson_dir = output_dir / "ndjson"
    if not ndjson_dir.is_dir():
        read_failures.append("ndjson: directory is missing")
    else:
        for path in sorted(ndjson_dir.glob("*.ndjson")):
            try:
                lines = path.read_text().splitlines()
            except OSError as exc:
                read_failures.append(f"{path.relative_to(output_dir)}: {exc}")
                continue
            for line_number, line in enumerate(lines, start=1):
                if not line.strip():
                    continue
                source = f"{path.relative_to(output_dir)}:{line_number}"
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise ValueError("expected a JSON object")
                except (ValueError, json.JSONDecodeError) as exc:
                    read_failures.append(f"{source}: {exc}")
                    continue
                records.append(ResourceRecord(payload=payload, source=source))

    bundles_dir = output_dir / "bundles"
    if not bundles_dir.is_dir():
        read_failures.append("bundles: directory is missing")
    else:
        for path in sorted(bundles_dir.glob("*.json")):
            try:
                bundle = _read_json_object(path)
                bundle_records.append(
                    ResourceRecord(payload=bundle, source=path.relative_to(output_dir).as_posix())
                )
                entries = bundle.get("entry")
                if not isinstance(entries, list):
                    raise ValueError("entry must be a list")
                if path.name == "shared.json":
                    continue
                patient_ids = [
                    f"Patient/{resource['id']}"
                    for entry in entries
                    if isinstance(entry, dict)
                    and isinstance((resource := entry.get("resource")), dict)
                    and resource.get("resourceType") == "Patient"
                    and isinstance(resource.get("id"), str)
                ]
                if len(patient_ids) != 1:
                    raise ValueError("patient bundle must contain exactly one Patient")
                encounter_count = sum(
                    1
                    for entry in entries
                    if isinstance(entry, dict)
                    and isinstance(entry.get("resource"), dict)
                    and entry["resource"].get("resourceType") == "Encounter"
                )
                bundle_encounter_counts[patient_ids[0]] = encounter_count
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                read_failures.append(f"{path.relative_to(output_dir)}: {exc}")

    return DatasetSnapshot(
        output_dir=output_dir,
        records=records,
        manifest=manifest,
        bundle_encounter_counts=bundle_encounter_counts,
        read_failures=read_failures,
        bundle_records=bundle_records,
        service_base_url=service_base_url,
    )
