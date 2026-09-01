"""Generation configuration model."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EncounterConfig(BaseModel):
    """Encounter count bounds."""

    min_per_patient: int = 10
    max_per_patient: int = 20


class GenerationConfig(BaseModel):
    """Top-level synthetic data generation configuration."""

    seed: int = 20260830
    patient_count: int = 1000
    encounters: EncounterConfig = Field(default_factory=EncounterConfig)
    history_years: int = 5
    output_dir: str = "artifacts"
