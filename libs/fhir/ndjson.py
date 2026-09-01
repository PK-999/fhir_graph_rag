"""NDJSON reader/writer for FHIR resources."""

from __future__ import annotations

import json
from pathlib import Path

from libs.fhir.models.base import FHIRResource


def write_ndjson(resources: list[FHIRResource], output_path: Path) -> int:
    """Write resources to an NDJSON file.

    Returns the number of resources written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w") as f:
        for resource in resources:
            json.dump(resource.to_dict(), f, default=str)
            f.write("\n")
            count += 1
    return count


def read_ndjson(input_path: Path) -> list[dict]:
    """Read an NDJSON file and return a list of resource dicts."""
    resources = []
    with input_path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                resources.append(json.loads(line))
    return resources
