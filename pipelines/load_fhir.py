"""CLI for loading synthetic FHIR data into a FHIR server."""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

from libs.fhir.loader import FHIRLoader, FHIRLoaderError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def load_bundles(bundles_dir: Path, fhir_url: str, concurrency: int = 10) -> dict:
    """Load all JSON bundles from the given directory into the FHIR server."""
    loader = FHIRLoader(base_url=fhir_url)

    bundle_files = list(bundles_dir.glob("*.json"))
    total_files = len(bundle_files)

    if total_files == 0:
        logger.warning(f"No bundle files found in {bundles_dir}")
        return {"total": 0, "success": 0, "failure": 0}

    logger.info(f"Found {total_files} bundles to upload.")

    # Process the shared bundle first if it exists
    shared_bundle = bundles_dir / "shared.json"
    if shared_bundle in bundle_files:
        bundle_files.remove(shared_bundle)
        logger.info("Uploading shared resources bundle first...")
        try:
            with shared_bundle.open() as f:
                data = json.load(f)
            await loader.upload_bundle(data)
            logger.info("Successfully uploaded shared bundle.")
        except Exception as e:
            logger.error(f"Failed to upload shared bundle: {e}")
            await loader.close()
            return {"total": 1, "success": 0, "failure": 1}

    semaphore = asyncio.Semaphore(concurrency)

    success_count = 1 if shared_bundle.exists() else 0
    failure_count = 0

    async def upload_worker(file_path: Path) -> bool:
        async with semaphore:
            try:
                with file_path.open() as f:
                    data = json.load(f)
                await loader.upload_bundle(data)
                return True
            except FHIRLoaderError as e:
                logger.error(f"Validation/Upload error for {file_path.name}: {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error uploading {file_path.name}: {e}")
                return False

    # Batch process remaining patient bundles
    logger.info(f"Uploading {len(bundle_files)} patient bundles with concurrency {concurrency}...")
    tasks = [upload_worker(p) for p in bundle_files]
    results = await asyncio.gather(*tasks)

    success_count += sum(1 for r in results if r)
    failure_count += sum(1 for r in results if not r)

    await loader.close()

    return {
        "total": total_files,
        "success": success_count,
        "failure": failure_count
    }


def main() -> None:
    """Run FHIR loader from command line."""
    parser = argparse.ArgumentParser(description="Load synthetic FHIR bundles into a server")
    parser.add_argument("--input", type=str, default="artifacts/bundles", help="Directory containing FHIR Bundle JSONs")
    parser.add_argument("--url", type=str, default="http://localhost:8080/fhir", help="FHIR Server base URL")
    parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent uploads")
    args = parser.parse_args()

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
        results = asyncio.run(load_bundles(input_dir, args.url, args.concurrency))
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
