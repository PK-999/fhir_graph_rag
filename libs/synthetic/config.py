"""Generation configuration model."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator


class EncounterConfig(BaseModel):
    """Encounter count bounds."""

    min_per_patient: int = Field(default=10, ge=1)
    max_per_patient: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> EncounterConfig:
        """Require a non-empty inclusive encounter range."""
        if self.max_per_patient < self.min_per_patient:
            raise ValueError("max_per_patient must be greater than or equal to min_per_patient")
        return self


class GenerationConfig(BaseModel):
    """Top-level synthetic data generation configuration."""

    seed: int = 20260830
    patient_count: int = Field(default=1000, ge=1)
    encounters: EncounterConfig = Field(default_factory=EncounterConfig)
    history_years: int = Field(default=5, ge=1)
    reference_date: date = date(2026, 8, 30)
    output_dir: str = "artifacts"
