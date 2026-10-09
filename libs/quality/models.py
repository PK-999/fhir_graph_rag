"""Typed quality-report and serialized-dataset models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ResourceRecord:
    """One serialized FHIR resource and its source location."""

    payload: dict[str, Any]
    source: str


@dataclass(frozen=True)
class DatasetSnapshot:
    """Read-only view of every artifact used by quality rules."""

    output_dir: Path
    records: list[ResourceRecord]
    manifest: dict[str, Any]
    bundle_encounter_counts: dict[str, int]
    read_failures: list[str]
    bundle_records: list[ResourceRecord] = field(default_factory=list)
    service_base_url: str | None = None


class RuleResult(BaseModel):
    """Outcome of one independently evaluated quality rule."""

    name: str
    status: Literal["pass", "fail"]
    checked: int = Field(ge=0)
    failures: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationReport(BaseModel):
    """Complete deterministic validation result for one dataset."""

    status: Literal["pass", "fail"]
    dataset_hash: str
    rules: dict[str, RuleResult]
    summary: dict[str, Any]
