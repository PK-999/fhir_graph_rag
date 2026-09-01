"""Cohort API router."""

import datetime
from typing import Any

from apps.api.app.dependencies import db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(prefix="/cohorts")

# ── Safety constants ──
MAX_CONDITION_CODES = 10
MAX_CODE_LENGTH = 20
QUERY_TIMEOUT_SECONDS = 30


async def get_neo4j_session():
    if not db.neo4j_driver:
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    async with db.neo4j_driver.session() as session:
        yield session


class CohortQuery(BaseModel):
    conditions: list[str] = Field(
        default=[],
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
async def search_conditions(q: str = "", limit: int = 50, session=Depends(get_neo4j_session)) -> list[dict[str, str]]:
    """Search for conditions for autocomplete."""
    query = """
    MATCH (c:Condition)
    WHERE (c.display_name IS NOT NULL AND toLower(c.display_name) CONTAINS toLower($q)) OR c.code CONTAINS $q
    RETURN DISTINCT c.code AS code, c.display_name AS name
    ORDER BY name ASC
    LIMIT $limit
    """
    result = await session.run(query, {"q": q, "limit": limit})
    return [record.data() async for record in result]


@router.post("/query")
async def query_cohort(query: CohortQuery, session=Depends(get_neo4j_session)) -> dict[str, Any]:
    """Execute a dynamic cohort query using Cypher."""

    cypher_parts = ["MATCH (p:Patient)"]
    params: dict[str, Any] = {}

    # Match conditions by code OR by substring in display_name
    if query.conditions:
        cypher_parts.append(
            "MATCH (p)<-[:HAS_SUBJECT|DURING_ENCOUNTER*1..2]-(c:Condition) WHERE any(cond IN $conditions WHERE c.code = cond OR toLower(c.display_name) CONTAINS toLower(cond))"
        )
        params["conditions"] = query.conditions

    if query.min_age is not None or query.max_age is not None:
        current_year = datetime.datetime.now(tz=datetime.timezone.utc).year
        where_clauses: list[str] = []
        if query.min_age is not None:
            max_birth_year = current_year - query.min_age
            params["max_birth_date"] = f"{max_birth_year}-12-31"
            where_clauses.append("p.birthDate <= $max_birth_date")
        if query.max_age is not None:
            min_birth_year = current_year - query.max_age
            params["min_birth_date"] = f"{min_birth_year}-01-01"
            where_clauses.append("p.birthDate >= $min_birth_date")
        cypher_parts.append("WHERE " + " AND ".join(where_clauses))

    cypher_parts.append("RETURN p.id AS id, p.display_name AS name, p.birthDate AS birthDate LIMIT 100")

    final_query = "\n".join(cypher_parts)

    result = await session.run(
        final_query,
        params,
        timeout=QUERY_TIMEOUT_SECONDS,
    )
    patients = [record.data() async for record in result]

    return {
        "query": final_query,
        "count": len(patients),
        "patients": patients
    }
