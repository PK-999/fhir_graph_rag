"""AI Assistant API router."""

import os
import re
from typing import Any

from apps.api.app.dependencies import db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI

router = APIRouter(prefix="/assistant")


class AssistantQuery(BaseModel):
    query: str


async def get_neo4j_session():
    if not db.neo4j_driver:
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    async with db.neo4j_driver.session() as session:
        yield session


def validate_cypher(cypher_query: str) -> None:
    """Ensure the Cypher query does not contain mutation operations."""
    query_upper = cypher_query.upper()
    banned_keywords = ["CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP", "CALL"]

    for word in banned_keywords:
        # Regex to match whole words only
        if re.search(r'\b' + word + r'\b', query_upper):
            raise ValueError(f"Mutation or unsafe keyword '{word}' is not allowed.")

    if "LIMIT" not in query_upper:
        raise ValueError("Queries must contain a LIMIT clause.")


def get_llm_client() -> AsyncOpenAI:
    base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("LLM_API_KEY", "ollama")
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


SYSTEM_PROMPT = """You are an expert Cypher developer for a Neo4j healthcare Knowledge Graph.
Your task is to translate natural language into a Cypher query.

Graph Schema:
This graph uses a dynamically flattened FHIR architecture. Every FHIR resource is a node. 
Nested properties are flattened into strings using a camelCase splitter (e.g. `name_0_family`, `code_coding_0_display`).
Edges are created from FHIR references, and their names correspond to the field. For example, `subject.reference` becomes a `[:SUBJECT]` edge.

Nodes: Patient, Condition, Observation, MedicationRequest, Encounter, Procedure.
Properties:
- Patient: id, name_0_given_0, name_0_family, birthDate, gender
- Condition: code_coding_0_code, code_coding_0_display
- Observation: code_coding_0_code, code_coding_0_display, valueQuantity_value, valueQuantity_unit
- MedicationRequest: medicationCodeableConcept_coding_0_code, medicationCodeableConcept_coding_0_display, status

Relationships (Path patterns to use):
To find conditions for a patient: MATCH (c:Condition)-[:SUBJECT]->(p:Patient)
To find medications for a patient: MATCH (m:MedicationRequest)-[:SUBJECT]->(p:Patient)
To find observations for a patient: MATCH (o:Observation)-[:SUBJECT]->(p:Patient)
To find encounters for a patient: MATCH (e:Encounter)-[:SUBJECT]->(p:Patient)
To find observations for an encounter: MATCH (o:Observation)-[:ENCOUNTER]->(e:Encounter)

Rules:
1. ALWAYS return a valid Cypher query and nothing else. Do NOT wrap in markdown like ```cypher.
2. ALWAYS include a LIMIT clause (e.g., LIMIT 50).
3. ALWAYS return 'p.id AS patient_id' and (p.name_0_given_0 + ' ' + p.name_0_family) AS name when querying for patients.
4. DO NOT use mutation keywords (CREATE, MERGE, DELETE, etc.).
5. Use CONTAINS with toLower() for text matching instead of exact codes. Example: `WHERE toLower(c.code_coding_0_display) CONTAINS "diabetes"`.
6. When filtering by counts (e.g., > 15 encounters), use WITH and count() instead of size() pattern expressions. Example: `MATCH (e:Encounter)-[:SUBJECT]->(p:Patient) WITH p, count(e) AS encounterCount WHERE encounterCount > 15 RETURN p, encounterCount`.
"""


@router.post("/query")
async def ask_assistant(query: AssistantQuery, session=Depends(get_neo4j_session)) -> dict[str, Any]:
    """Process a natural language query using a Text-to-Cypher LLM."""
    client = get_llm_client()
    model = os.getenv("LLM_MODEL", "llama3.1")

    # Step 1: Generate Cypher
    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Generate a Cypher query for: {query.query}"}
            ],
            temperature=0.0
        )
        cypher = completion.choices[0].message.content.strip()
        
        # Clean markdown if the model hallucinated it
        if cypher.startswith("```"):
            cypher = re.sub(r"^```(?:cypher)?\n?", "", cypher)
            cypher = re.sub(r"\n?```$", "", cypher).strip()
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM failed to generate Cypher: {e}")

    # Step 2: Validate and execute
    try:
        validate_cypher(cypher)
        result = await session.run(cypher)
        records = [record.data() async for record in result]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {e}")

    # Step 3: Summarize results
    summary_prompt = f"The user asked: '{query.query}'. The database returned {len(records)} records. Provide a very brief, friendly one-sentence summary of the results. Do not mention cypher or the database."
    try:
        summary_completion = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": summary_prompt}
            ],
            temperature=0.7
        )
        explanation = summary_completion.choices[0].message.content.strip()
    except Exception:
        explanation = f"Found {len(records)} results matching your query."

    # Build evidence references from results
    evidence = []
    for rec in records:
        if "patient_id" in rec:
            evidence.append({"type": "Patient", "id": rec["patient_id"], "label": rec.get("name", "Unknown")})

    return {
        "answer": explanation,
        "cypher": cypher,
        "results": records,
        "evidence": evidence
    }
