"""Persist stage-confirmed audit records for the single-dataset portfolio demo."""

import hashlib
import json
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

TRANSFORMER_VERSION = "fhirgraph-r4-v2"

# Existing volumes do not rerun Docker initialization scripts. Keep legacy rows
# nullable: their missing source evidence must never be fabricated by migration.
PROVENANCE_MIGRATION = """
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS canonical_id TEXT;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS source_artifact TEXT;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS source_location TEXT;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS source_line INTEGER;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64);
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS dataset_hash VARCHAR(64);
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS transformer_version VARCHAR(64);
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS target_identity TEXT;
ALTER TABLE ingestion_events ADD COLUMN IF NOT EXISTS confirmed_stage VARCHAR(32);
CREATE INDEX IF NOT EXISTS idx_ingestion_canonical_id ON ingestion_events(canonical_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ingestion_confirmed_event
ON ingestion_events(run_id, target_system, resource_type, resource_id, confirmed_stage);
"""


def canonical_sha256(payload: Any) -> str:
    """Hash the exact serialized values, independent of JSON object key order."""
    return hashlib.sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def target_identity(uri: str, user: str | None = None) -> str:
    """Bind to a destination/principal without writing a password into artifacts."""
    parts = urlsplit(uri)
    if not parts.scheme or not parts.hostname:
        raise ValueError("Target must be an absolute URI")
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    if parts.port:
        host += f":{parts.port}"
    principal = user if user is not None else parts.username
    clean = urlunsplit((parts.scheme.lower(), host, parts.path.rstrip("/"), "", ""))
    # Queries/fragments could change the destination and might contain credentials.
    if parts.query or parts.fragment:
        raise ValueError("Target URI must not include query parameters or fragments")
    return f"{clean}|user={principal}" if principal else clean


class IngestionCheckpoint:
    """Atomically persist successful batches; ambiguous writes are replayed idempotently."""

    def __init__(self, path: Path, binding: dict[str, Any], *, resume: bool = True) -> None:
        self.path = path
        self.state: dict[str, Any] = {"version": 1, "binding": binding, "completed": {}}
        if path.exists():
            try:
                saved = json.loads(path.read_text())
            except (OSError, ValueError) as exc:
                raise ValueError(f"Invalid checkpoint: {path}") from exc
            if not isinstance(saved, dict):
                raise ValueError(f"Invalid checkpoint: {path}")
            if saved.get("version") != 1 or saved.get("binding") != binding:
                raise ValueError(
                    f"checkpoint binding mismatch: {path}; use the same dataset and destination, or a separate checkpoint for an isolated store"
                )
            if not isinstance(saved.get("completed"), dict):
                raise ValueError(f"Invalid checkpoint completed batches: {path}")
            if resume:
                self.state = saved
        # Bind even interrupted schema/connectivity attempts before any store work.
        self._persist()

    def confirmed(self, key: str, digest: str) -> bool:
        completed = self.state["completed"]
        if key in completed and completed[key] != digest:
            raise ValueError(f"checkpoint batch content mismatch: {key}")
        return key in completed

    def confirm(self, key: str, digest: str) -> None:
        self.state["completed"][key] = digest
        self._persist()

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
        try:
            with temporary.open("w") as handle:
                json.dump(self.state, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)


def default_checkpoint(source: Path, stage: str) -> Path:
    # Never place checkpoints inside managed bundles/ndjson directories: their
    # bytes would otherwise become part of the next generated dataset manifest.
    base = source.parent
    if source.is_file() and (base.parent / "dataset_manifest.json").exists():
        base = base.parent
    return base / ".checkpoints" / f"{stage}.json"


def dataset_identity(source: Path, source_digest: str, file_hashes: dict[str, str]) -> str:
    """Use a manifest hash only when all this stage's files match its manifest."""
    root = source.parent
    manifest_path = root / "dataset_manifest.json"
    if not manifest_path.exists():
        return source_digest
    manifest = json.loads(manifest_path.read_text())
    files = manifest.get("files", {})
    if source.is_dir():
        expected = {name for name in files if name.startswith(f"{source.name}/")}
        actual = {f"{source.name}/{name}" for name in file_hashes}
        if expected != actual:
            raise ValueError("Source artifact set does not match dataset manifest")
    for name, digest in file_hashes.items():
        relative = f"{source.name}/{name}" if source.is_dir() else name
        if files.get(relative) != digest:
            raise ValueError(f"Source artifact does not match dataset manifest: {relative}")
    dataset_hash = manifest.get("dataset_hash")
    if not isinstance(dataset_hash, str) or len(dataset_hash) != 64:
        raise ValueError("Invalid dataset manifest hash")
    return dataset_hash


class RunAudit:
    def __init__(self, connection: Any, run_id: str, snapshot: dict[str, Any]) -> None:
        self.connection, self.run_id, self.snapshot = connection, run_id, snapshot
        self._stage_started: dict[str, float] = {}

    async def start(self) -> None:
        await self.connection.execute(PROVENANCE_MIGRATION)
        await self.connection.execute(
            "INSERT INTO pipeline_runs (run_id, pipeline_name, config_snapshot) VALUES ($1, 'full_pipeline', $2::jsonb)",
            self.run_id,
            json.dumps(self.snapshot),
        )

    async def stage(self, module: str, status: str) -> None:
        self.snapshot["stages"][module] = status
        timings = self.snapshot.setdefault("stage_timings", {})
        timing = timings.setdefault(module, {})
        timing["status"] = status
        if status == "running":
            self._stage_started[module] = time.monotonic()
            timing["started_at"] = datetime.now(UTC).isoformat()
        elif module in self._stage_started:
            timing["elapsed_seconds"] = time.monotonic() - self._stage_started.pop(module)
            timing["completed_at"] = datetime.now(UTC).isoformat()
        await self.connection.execute(
            "UPDATE pipeline_runs SET config_snapshot = $2::jsonb WHERE run_id = $1",
            self.run_id,
            json.dumps(self.snapshot),
        )

    async def quality(self, output: Path) -> None:
        report_path = output / "data_quality_summary.json"
        if not report_path.exists():
            return
        report = json.loads(report_path.read_text())
        self.snapshot["dataset_hash"] = report["dataset_hash"]
        rows = [
            (self.run_id, name, rule["status"] == "pass", json.dumps(rule))
            for name, rule in report["rules"].items()
        ]
        async with self.connection.transaction():
            await self.connection.execute(
                "DELETE FROM data_quality_results WHERE run_id = $1", self.run_id
            )
            await self.connection.executemany(
                "INSERT INTO data_quality_results (run_id, rule_name, passed, details) VALUES ($1,$2,$3,$4::jsonb)",
                rows,
            )
        await self.stage("validate", self.snapshot["stages"].get("validate", "running"))

    async def guard_dataset(self) -> None:
        registered = await self.connection.fetch(
            """SELECT config_snapshot->>'dataset_hash' AS dataset_hash FROM pipeline_runs
            WHERE run_id <> $1 AND (status = 'success' OR
                config_snapshot->'stages'->>'load_fhir' IN ('running', 'success', 'failed'))""",
            self.run_id,
        )
        if any(row["dataset_hash"] != self.snapshot["dataset_hash"] for row in registered):
            raise ValueError(
                "A different or unregistered dataset already exists. Use a fresh isolated Compose project before ingesting another dataset."
            )

    async def ingestion(self, output: Path, target: str) -> None:
        """Write source provenance only after this entire target stage returned success."""
        stage = "load_fhir" if target == "hapi_fhir" else "build_graph"
        destination = self.snapshot["targets"][target]
        self.verify_source_manifest(output, target)
        batch: list[tuple[Any, ...]] = []
        async with self.connection.transaction():
            for resource, artifact, location, number in self.source_records(output, target):
                batch.append(
                    (
                        self.run_id,
                        resource["resourceType"],
                        resource["id"],
                        "upserted",
                        target,
                        f"{resource['resourceType']}/{resource['id']}",
                        artifact,
                        location,
                        number,
                        canonical_sha256(resource),
                        self.snapshot["dataset_hash"],
                        TRANSFORMER_VERSION,
                        destination,
                        stage,
                    )
                )
                if len(batch) == 1000:
                    await self.write_events(batch)
                    batch = []
            if batch:
                await self.write_events(batch)
            # A concurrent source change invalidates this transaction's evidence.
            self.verify_source_manifest(output, target)

    def verify_source_manifest(self, output: Path, target: str) -> None:
        manifest = json.loads((output / "dataset_manifest.json").read_bytes())
        if manifest.get("dataset_hash") != self.snapshot["dataset_hash"]:
            raise ValueError("Source artifact dataset manifest changed after validation")
        directory, extension = (
            ("bundles", "*.json") if target == "hapi_fhir" else ("ndjson", "*.ndjson")
        )
        sources = sorted((output / directory).glob(extension))
        expected = {name for name in manifest.get("files", {}) if name.startswith(f"{directory}/")}
        if {source.relative_to(output).as_posix() for source in sources} != expected:
            raise ValueError("Source artifact set does not match dataset manifest")
        for source in sources:
            digest = hashlib.sha256()
            with source.open("rb") as handle:
                while raw := handle.read(1024 * 1024):
                    digest.update(raw)
            artifact = source.relative_to(output).as_posix()
            if manifest.get("files", {}).get(artifact) != digest.hexdigest():
                raise ValueError(f"Source artifact does not match dataset manifest: {artifact}")

    @staticmethod
    def source_records(
        output: Path, target: str
    ) -> Iterator[tuple[dict[str, Any], str, str, int | None]]:
        if target == "hapi_fhir":
            for source in sorted((output / "bundles").glob("*.json")):
                for number, entry in enumerate(json.loads(source.read_bytes())["entry"]):
                    yield (
                        entry["resource"],
                        source.relative_to(output).as_posix(),
                        f"entry:{number}",
                        None,
                    )
        else:
            for source in sorted((output / "ndjson").glob("*.ndjson")):
                with source.open() as handle:
                    for number, line in enumerate(handle, 1):
                        if line.strip():
                            yield (
                                json.loads(line),
                                source.relative_to(output).as_posix(),
                                f"line:{number}",
                                number,
                            )

    async def write_events(self, batch: list[tuple[Any, ...]]) -> None:
        await self.connection.executemany(
            """INSERT INTO ingestion_events
            (run_id, resource_type, resource_id, action, target_system, canonical_id,
             source_artifact, source_location, source_line, content_sha256, dataset_hash,
             transformer_version, target_identity, confirmed_stage)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
            ON CONFLICT DO NOTHING""",
            batch,
        )

    async def finish(self, status: str, error: str | None = None) -> None:
        await self.connection.execute(
            "UPDATE pipeline_runs SET status = $2, error_message = $3, completed_at = NOW() WHERE run_id = $1",
            self.run_id,
            status,
            error,
        )
