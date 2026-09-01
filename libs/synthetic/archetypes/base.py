"""Base class for clinical scenario archetypes.

Each archetype represents a longitudinal clinical pattern (e.g., diabetes,
hypertension) and generates appropriate FHIR resources during encounters.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime

from libs.fhir.models.base import FHIRResource
from libs.fhir.models.datatypes import Reference


class PatientState:
    """Mutable clinical state that evolves across encounters."""

    def __init__(self) -> None:
        self.active_conditions: dict[str, datetime] = {}  # code -> onset datetime
        self.active_medications: dict[str, str] = {}  # code -> medication_request_id
        self.latest_observations: dict[str, float] = {}  # code -> latest value
        self.flags: dict[str, bool] = {}  # arbitrary flags for state machines


class ClinicalArchetype(ABC):
    """Abstract base for clinical scenario templates."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable archetype name."""
        ...

    @abstractmethod
    def apply(
        self,
        patient_id: str,
        encounter_id: str,
        encounter_time: datetime,
        state: PatientState,
        rng: random.Random,
        practitioner_ref: Reference,
        id_factory_fn: object,
    ) -> list[FHIRResource]:
        """Generate resources for a single encounter.

        Args:
            patient_id: Patient resource ID (e.g., "p-000001")
            encounter_id: Encounter resource ID
            encounter_time: When the encounter occurred
            state: Mutable patient state that persists across encounters
            rng: Seeded random number generator
            practitioner_ref: Reference to the encounter's practitioner
            id_factory_fn: Callable to generate resource IDs

        Returns:
            List of FHIR resources generated during this encounter.
        """
        ...

    def is_compatible(self, gender: str, age: int) -> bool:
        """Check if this archetype is applicable for a patient's demographics.

        Override in subclasses to apply age/gender constraints.
        """
        return True
