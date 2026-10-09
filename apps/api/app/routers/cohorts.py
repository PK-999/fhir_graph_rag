"""Cohort API router."""

import datetime
from typing import Any

from apps.api.app.dependencies import get_neo4j_session
from fastapi import APIRouter, Depends, Query
from neo4j import Query as Neo4jQuery
from pydantic import AliasChoices, BaseModel, Field, field_validator

router = APIRouter(prefix="/cohorts")

# ── Safety constants ──
MAX_CONDITION_CODES = 10
MAX_CODE_LENGTH = 20
QUERY_TIMEOUT_SECONDS = 30


class CohortQuery(BaseModel):
    conditions: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("conditions", "condition_codes"),
        max_length=MAX_CONDITION_CODES,
        description=f"Up to {MAX_CONDITION_CODES} FHIR condition codes or names.",
    )
    min_age: int | None = Field(default=None, ge=0, le=150)
    max_age: int | None = Field(default=None, ge=0, le=150)

    @field_validator("conditions", mode="before")
    @classmethod
    def _validate_codes(cls, v: list[str]) -> list[str]:
        if not isinstance(v, list):
            raise ValueError("conditions must be a list")
        for code in v:
            if not isinstance(code, str) or len(code) > MAX_CODE_LENGTH:
                raise ValueError(
                    f"Each condition must be a string of at most {MAX_CODE_LENGTH} characters"
                )
            if not code.strip():
                raise ValueError("Conditions must not be blank")
        return v


@router.get("/conditions")
async def search_conditions(
    q: str = "",
    limit: int = Query(default=50, ge=1, le=100),
    session: Any = Depends(get_neo4j_session),
) -> list[dict[str, str]]:
    """Search for conditions for autocomplete."""
    query = """
    MATCH (c:Condition)
    WHERE toLower(coalesce(c.code_coding_0_display, c.code_text, '')) CONTAINS toLower($q)
          OR c.code_coding_0_code CONTAINS $q
    RETURN DISTINCT c.code_coding_0_code AS code,
           coalesce(c.code_coding_0_display, c.code_text) AS name
    ORDER BY name ASC
    LIMIT $limit
    """
    result = await session.run(
        Neo4jQuery(query, timeout=QUERY_TIMEOUT_SECONDS), {"q": q, "limit": limit}
    )
    return [record.data() async for record in result]


@router.post("/query")
async def query_cohort(
    query: CohortQuery, session: Any = Depends(get_neo4j_session)
) -> dict[str, Any]:
    """Execute a dynamic cohort query using Cypher."""

    cypher_parts = ["MATCH (p:Patient)"]
    params: dict[str, Any] = {}
    where_clauses: list[str] = []

    # A condition may point directly to its patient or through an encounter.
    if query.conditions:
        cypher_parts.append("MATCH (p)<-[:SUBJECT|ENCOUNTER*1..2]-(c:Condition)")
        where_clauses.append(
            "any(cond IN $conditions WHERE c.code_coding_0_code = cond OR "
            "toLower(coalesce(c.code_coding_0_display, c.code_text, '')) CONTAINS toLower(cond))"
        )
        params["conditions"] = query.conditions

    if query.min_age is not None or query.max_age is not None:
        params["today"] = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
        age = "duration.between(date(p.birth_date), date($today)).years"
        if query.min_age is not None:
            params["min_age"] = query.min_age
            where_clauses.append(f"{age} >= $min_age")
        if query.max_age is not None:
            params["max_age"] = query.max_age
            where_clauses.append(f"{age} <= $max_age")

    if where_clauses:
        cypher_parts.append("WHERE " + " AND ".join(where_clauses))

    cypher_parts.append(
        "RETURN DISTINCT p.id AS id, "
        "coalesce(p.name_0_text, trim(coalesce(p.name_0_given_0, '') + ' ' + "
        "coalesce(p.name_0_family, ''))) AS name, p.birth_date AS birthDate LIMIT 100"
    )

    final_query = "\n".join(cypher_parts)

    result = await session.run(
        Neo4jQuery(final_query, timeout=QUERY_TIMEOUT_SECONDS),
        params,
    )
    patients = [record.data() async for record in result]

    return {"query": final_query, "count": len(patients), "patients": patients}
