"""Validate local-model fact selections and render only exact retrieved values."""

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceClaim(BaseModel):
    """A claim can select an existing fact; it cannot supply clinical prose."""

    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    evidence_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9]*/[A-Za-z0-9.-]{1,64}$")
    field: str = Field(min_length=1, max_length=200)
    value: str | int | float | bool


class ClaimSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    claims: list[EvidenceClaim] = Field(min_length=1, max_length=50)


def validate_claims(content: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject the entire selection if any ID, path, value, or duplicate is invalid."""
    if len(content) > 64000:
        raise ValueError("Claim selection exceeds the response bound")
    selection = ClaimSelection.model_validate_json(content)
    facts = {item["id"]: item["facts"] for item in evidence}
    seen: set[tuple[str, str]] = set()
    claims = []
    for claim in selection.claims:
        key = (claim.evidence_id, claim.field)
        resource_facts = facts.get(claim.evidence_id, {})
        if key in seen or claim.field not in resource_facts:
            raise ValueError("Claim must select a unique retrieved resource fact")
        source_value = resource_facts[claim.field]
        if isinstance(source_value, bool) or isinstance(claim.value, bool):
            same = type(source_value) is type(claim.value) and source_value == claim.value
        else:
            same = source_value == claim.value
        if not same:
            raise ValueError("Claim value differs from retrieved evidence")
        seen.add(key)
        # Return the retrieved value, never an unchecked model string.
        claims.append(
            {"evidence_id": claim.evidence_id, "field": claim.field, "value": source_value}
        )
    return claims


def render_claims(claims: list[dict[str, Any]]) -> str:
    """Mechanical source-labelled rendering cannot introduce clinical inferences."""
    return "\n".join(
        f"{claim['evidence_id']}: {claim['field']} = {json.dumps(claim['value'], ensure_ascii=False, allow_nan=False)}."
        for claim in claims
    )


def summary_fields(
    *,
    requested: bool = False,
    status: str = "not_requested",
    model: str | None = None,
    claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected = claims or []
    return {
        "claims": selected,
        "summary": render_claims(selected) if selected else None,
        "summary_metadata": {
            "requested": requested,
            "status": status,
            "model": model,
            "claim_count": len(selected),
        },
    }
