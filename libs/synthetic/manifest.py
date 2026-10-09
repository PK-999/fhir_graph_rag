"""Deterministic manifest creation for generated dataset artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from libs.synthetic.config import GenerationConfig


def build_dataset_manifest(
    output_dir: Path,
    config: GenerationConfig,
) -> dict[str, Any]:
    """Hash every managed Bundle and NDJSON file in relative-path order."""
    managed_files = sorted(
        path
        for directory_name in ("bundles", "ndjson")
        for path in (output_dir / directory_name).glob("**/*")
        if path.is_file()
    )
    dataset_digest = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for path in managed_files:
        relative_path = path.relative_to(output_dir).as_posix()
        content = path.read_bytes()
        file_hashes[relative_path] = hashlib.sha256(content).hexdigest()
        dataset_digest.update(relative_path.encode())
        dataset_digest.update(b"\0")
        dataset_digest.update(content)
        dataset_digest.update(b"\0")

    return {
        "manifest_version": 1,
        "generation": config.model_dump(mode="json", exclude={"output_dir"}),
        "dataset_hash": dataset_digest.hexdigest(),
        "files": file_hashes,
        "file_count": len(file_hashes),
    }
