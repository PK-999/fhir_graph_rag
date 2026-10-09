"""CLI for loading synthetic FHIR data into a FHIR server."""

import argparse
import asyncio
import hashlib
import json
import logging
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from libs.fhir.loader import FHIRLoader
from libs.fhir.references import ReferenceIndex, iter_references
from libs.fhir.validation import validate_resource
from pipelines.config import PipelineSettings
from pipelines.metadata import (
    TRANSFORMER_VERSION,
    IngestionCheckpoint,
    dataset_identity,
    default_checkpoint,
    target_identity,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _preflight(
    bundles_dir: Path, spool: Path, fhir_url: str
) -> tuple[list[Path], str, dict[str, str]]:
    files = sorted(bundles_dir.glob("*.json"))
    if not files:
        raise ValueError(f"No bundle files found in {bundles_dir}")
    index = ReferenceIndex(service_base_url=fhir_url)
    digest = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for path in files:
        raw = path.read_bytes()
        digest.update(path.name.encode() + b"\0" + raw + b"\0")
        file_hashes[path.name] = hashlib.sha256(raw).hexdigest()
        try:
            data = json.loads(raw)
            if (
                not isinstance(data, dict)
                or data.get("resourceType") != "Bundle"
                or data.get("type") != "transaction"
            ):
                raise ValueError("expected a FHIR transaction Bundle")
            # Validate the enclosing Bundle as well as its nested resource payloads.
            issues = validate_resource(data)
            if issues:
                raise ValueError("; ".join(f"{issue.path}: {issue.message}" for issue in issues))
            entries = data.get("entry")
            if not isinstance(entries, list) or not entries:
                raise ValueError("transaction Bundle must have entries")
            for number, entry in enumerate(entries):
                if not isinstance(entry, dict) or not isinstance(entry.get("resource"), dict):
                    raise ValueError(f"entry {number}: expected a resource object")
                resource = entry["resource"]
                canonical = f"{resource.get('resourceType')}/{resource.get('id')}"
                if canonical in index.known_ids:
                    raise ValueError(f"entry {number}: duplicate resource ID: {canonical}")
                request = entry.get("request", {})
                if (
                    not isinstance(request, dict)
                    or request.get("method") != "PUT"
                    or request.get("url") != canonical
                ):
                    raise ValueError(f"entry {number}: requires idempotent PUT to {canonical}")
                index.add(resource, full_url=entry.get("fullUrl"), bundle_scope=path.name)
            (spool / path.name).write_bytes(raw)
        except Exception as exc:
            raise ValueError(f"{path}: {exc}") from exc
    # Resolve only after the complete identity/Bundle alias set has been indexed.
    for path in files:
        data = json.loads((spool / path.name).read_bytes())
        for number, entry in enumerate(data["entry"]):
            resource = entry["resource"]
            for occurrence in iter_references(resource):
                resolved = index.resolve(
                    occurrence.reference, resource, bundle_scope=path.name, path=occurrence.path
                )
                if resolved.status not in ("resolved", "contained"):
                    raise ValueError(
                        f"{path}:entry:{number}:{occurrence.path}: reference {occurrence.reference!r}: {resolved.diagnostic}"
                    )
    return files, digest.hexdigest(), file_hashes


async def load_bundles(
    bundles_dir: Path,
    fhir_url: str,
    concurrency: int = 10,
    *,
    checkpoint_path: Path | None = None,
    resume: bool = True,
) -> dict[str, int]:
    """Preflight every Bundle, then upload with bounded tasks and durable confirmations."""
    if concurrency < 1:
        raise ValueError("Concurrency must be at least 1")
    with tempfile.TemporaryDirectory(prefix="fhirgraph-upload-") as directory:
        spool = Path(directory)
        files, digest, hashes = _preflight(bundles_dir, spool, fhir_url)
        checkpoint = IngestionCheckpoint(
            checkpoint_path or default_checkpoint(bundles_dir, "load_fhir"),
            {
                "stage": "load_fhir",
                "target": target_identity(fhir_url),
                "dataset_hash": dataset_identity(bundles_dir, digest, hashes),
                "source_digest": digest,
                "transformer_version": TRANSFORMER_VERSION,
            },
            resume=resume,
        )
        # The shared dependency transaction always completes before patient uploads.
        shared = next((path for path in files if path.name == "shared.json"), None)
        if shared:
            files.remove(shared)
            files.insert(0, shared)
        loader = FHIRLoader(base_url=fhir_url)
        success = failure = 0

        async def upload(path: Path) -> bool:
            key = f"bundle:{path.name}"
            if checkpoint.confirmed(key, hashes[path.name]):
                return True
            try:
                data: dict[str, Any] = json.loads((spool / path.name).read_bytes())
                await loader.upload_bundle(data)
                checkpoint.confirm(key, hashes[path.name])
                return True
            except Exception as exc:
                logger.error("Failed to upload %s: %s", path.name, exc)
                return False

        try:
            if shared:
                if not await upload(shared):
                    return {"total": len(files), "success": 0, "failure": len(files)}
                success += 1
                remaining = files[1:]
            else:
                remaining = files
            # At most concurrency tasks exist, including queued tasks. No giant gather.
            for offset in range(0, len(remaining), concurrency):
                results = await asyncio.gather(
                    *(upload(path) for path in remaining[offset : offset + concurrency])
                )
                success += sum(results)
                failure += sum(not result for result in results)
            return {"total": len(files), "success": success, "failure": failure}
        finally:
            await loader.close()


def main() -> None:
    """Run FHIR loader from command line."""
    parser = argparse.ArgumentParser(description="Load synthetic FHIR bundles into a server")
    config = PipelineSettings()
    parser.add_argument(
        "--input",
        type=str,
        default="artifacts/bundles",
        help="Directory containing FHIR Bundle JSONs",
    )
    parser.add_argument(
        "--url", type=str, default=config.hapi_fhir_url, help="FHIR Server base URL"
    )
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent uploads")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        help="Checkpoint path (default: output/.checkpoints/load_fhir.json, outside source artifacts)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Replay the same bound dataset using idempotent PUT",
    )
    args = parser.parse_args()
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")

    input_dir = Path(args.input)
    if not input_dir.exists() or not input_dir.is_dir():
        logger.error(f"Input directory does not exist: {input_dir}")
        sys.exit(1)

    print("🏥 FHIRGraph Ingestion Loader")
    print(f"   Source: {input_dir}")
    print(f"   Target: {args.url}")
    print(f"   Concurrency: {args.concurrency}")
    print()

    start = time.time()

    try:
        options: dict[str, Any] = {}
        if args.checkpoint:
            options["checkpoint_path"] = args.checkpoint
        if args.no_resume:
            options["resume"] = False
        results = asyncio.run(load_bundles(input_dir, args.url, args.concurrency, **options))
    except ValueError as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        print("\nUpload interrupted by user.")
        sys.exit(1)

    elapsed = time.time() - start

    print(f"\n✅ Upload complete in {elapsed:.1f}s")
    print(f"   Total bundles: {results['total']}")
    print(f"   Success: {results['success']}")
    print(f"   Failed:  {results['failure']}")

    if results["failure"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
