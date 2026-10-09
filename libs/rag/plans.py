"""Strict clinical intents and deliberately narrow demo question parsing."""

import re
from typing import Literal, Self, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

Intent = Literal[
    "patient_list",
    "condition_cohort",
    "latest_lab_medication",
    "patient_history",
    "medication_cohort",
    "patient_lab_history",
]


class QueryPlan(BaseModel):
    """Only these fields can influence the application-owned query templates."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    intent: Intent
    limit: int = Field(default=20, ge=1, le=100)
    condition_code: str | None = Field(default=None, min_length=1, max_length=64)
    lab_code: str | None = Field(default=None, min_length=1, max_length=64)
    medication_code: str | None = Field(default=None, min_length=1, max_length=64)
    threshold: float | None = Field(default=None, ge=-100000, le=100000)
    comparison: Literal["gt", "gte", "lt", "lte"] = "gt"
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    patient_id: str | None = Field(default=None, pattern=r"^Patient/[A-Za-z0-9.-]{1,64}$")

    @model_validator(mode="after")
    def validate_intent(self) -> Self:
        required = {
            "patient_list": set(),
            "condition_cohort": {"condition_code"},
            "latest_lab_medication": {"lab_code", "medication_code", "threshold", "unit"},
            "patient_history": {"patient_id"},
            "medication_cohort": {"medication_code"},
            "patient_lab_history": {"patient_id"},
        }[self.intent]
        optional = {
            "latest_lab_medication": {"condition_code"},
            "medication_cohort": {"condition_code"},
            "patient_lab_history": {"lab_code"},
        }.get(self.intent, set())
        clinical = {
            "condition_code",
            "lab_code",
            "medication_code",
            "threshold",
            "unit",
            "patient_id",
        }
        present = {name for name in clinical if getattr(self, name) is not None}
        if not required <= present or present - required - optional:
            raise ValueError(f"Fields do not match intent {self.intent}")
        if self.intent != "latest_lab_medication" and self.comparison != "gt":
            raise ValueError("Comparison applies only to latest_lab_medication")
        return self


def parse_question(question: str) -> QueryPlan | None:
    """Recognize complete supported questions, never discard an unknown filter."""
    original = re.sub(r"\s+", " ", question.strip().rstrip("?.")).strip()
    original = re.sub(r"^(?:(?:can|could|would) you |please )", "", original, flags=re.IGNORECASE)
    text = original.lower()
    listing = re.fullmatch(r"(?:list|show|find)(?: me)? (?:(\d+|five|ten|twenty) )?patients", text)
    if listing:
        limit_text = listing.group(1)
        limits = {"five": 5, "ten": 10, "twenty": 20}
        limit = limits.get(
            limit_text, int(limit_text) if limit_text and limit_text.isdigit() else 20
        )
        if 1 <= limit <= 100:
            return QueryPlan(intent="patient_list", limit=limit)
        return None
    history = re.fullmatch(
        r"(?:(?:show|get) |what is )(?:the )?history for (Patient/[A-Za-z0-9.-]{1,64})",
        original,
        flags=re.IGNORECASE,
    )
    if history:
        identifier = history.group(1).split("/", 1)[1]
        return QueryPlan(intent="patient_history", patient_id=f"Patient/{identifier}")
    lab_history = re.fullmatch(
        r"(?:(?:(?:show|get|list) |what is )(?:the )?(?:(hba1c|hemoglobin a1c|lab|laboratory) (?:history|results))|what are (?:the )?(hba1c|hemoglobin a1c|lab|laboratory) results) for (Patient/[A-Za-z0-9.-]{1,64})",
        original,
        flags=re.IGNORECASE,
    )
    if lab_history:
        lab = (lab_history.group(1) or lab_history.group(2)).lower()
        patient_id = "Patient/" + lab_history.group(3).split("/", 1)[1]
        return QueryPlan(
            intent="patient_lab_history",
            patient_id=patient_id,
            lab_code="4548-4" if lab in {"hba1c", "hemoglobin a1c"} else None,
        )
    medication = re.fullmatch(
        r"(?:(?:find|show|list)(?: me)? patients (?:with|on)|which patients (?:have|are on)|who (?:has|is on)) active (?:metformin(?: (?:prescriptions|medication requests))?|prescriptions for metformin)(?: (?:with|and) (.+))?",
        text,
    )
    if medication:
        condition_code = _condition_code(medication.group(1)) if medication.group(1) else None
        if medication.group(1) and condition_code is None:
            return None
        return QueryPlan(
            intent="medication_cohort", medication_code="6809", condition_code=condition_code
        )
    condition = re.fullmatch(
        r"(?:(?:find|show|list)(?: me)? patients (?:with|diagnosed with)|which patients (?:have|are diagnosed with)|who has) (?:(?:condition(?: code)?|a diagnosis of) )?(.+)",
        text,
    )
    if condition:
        code = _condition_code(condition.group(1))
        if code:
            return QueryPlan(intent="condition_cohort", condition_code=code)
    latest = re.fullmatch(
        r"(?:(?:find|show|list)(?: me)? patients (?:whose |with )?|which patients (?:have |have a |have their )?)latest (?:hba1c|hemoglobin a1c) (?:is )?(above|over|greater than|>|at least|>=|below|under|<|at most|<=) ?(\d+(?:\.\d+)?) ?%? (?:with|and|on|who have|who are on|and have|and are on) active metformin(?: prescriptions)?(?: (?:with|and) (.+))?",
        text,
    )
    if latest and float(latest.group(2)) <= 100000:
        condition_code = _condition_code(latest.group(3)) if latest.group(3) else None
        if latest.group(3) and condition_code is None:
            return None
        comparison = {
            "above": "gt",
            "over": "gt",
            "greater than": "gt",
            ">": "gt",
            "at least": "gte",
            ">=": "gte",
            "below": "lt",
            "under": "lt",
            "<": "lt",
            "at most": "lte",
            "<=": "lte",
        }[latest.group(1)]
        return QueryPlan(
            intent="latest_lab_medication",
            lab_code="4548-4",
            medication_code="6809",
            threshold=float(latest.group(2)),
            unit="%",
            comparison=cast("Literal['gt', 'gte', 'lt', 'lte']", comparison),
            condition_code=condition_code,
        )
    return None


def _condition_code(term: str) -> str | None:
    code = {
        "type 2 diabetes": "44054006",
        "type 2 diabetes mellitus": "44054006",
        "diabetes": "44054006",
        "hypertension": "38341003",
    }.get(term)
    return term if code is None and re.fullmatch(r"\d{3,12}", term) else code
