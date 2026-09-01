"""Timeline API router — chronological clinical events for a patient."""

from typing import Any

from apps.api.app.dependencies import db
from fastapi import APIRouter, Depends, HTTPException

router = APIRouter(prefix="/patients")

QUERY_TIMEOUT_SECONDS = 30


async def get_neo4j_session():
    if not db.neo4j_driver:
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    async with db.neo4j_driver.session() as session:
        yield session


@router.get("/{patient_id}/timeline")
async def get_patient_timeline(
    patient_id: str,
    session=Depends(get_neo4j_session),
) -> dict[str, Any]:
    """Return all clinical events for a patient ordered by date.

    Each event includes its type, display name, code, date, and
    the encounter it belongs to (if any).
    """
    patient_fhir_id = f"Patient/{patient_id}"

    query = """
    MATCH (p:Patient {id: $id})

    // Encounters (anchor events)
    OPTIONAL MATCH (p)<-[:HAS_SUBJECT]-(e:Encounter)
    WITH p, collect(DISTINCT e) AS encounters

    // Resources linked to patient directly or via encounter
    OPTIONAL MATCH (p)<-[:HAS_SUBJECT]-(c:Condition)
    WITH p, encounters, collect(DISTINCT c) AS conditions

    OPTIONAL MATCH (p)<-[:HAS_SUBJECT|DURING_ENCOUNTER*1..2]-(o:Observation)
    WITH p, encounters, conditions, collect(DISTINCT o) AS observations

    OPTIONAL MATCH (p)<-[:HAS_SUBJECT|DURING_ENCOUNTER*1..2]-(m:MedicationRequest)
    WITH p, encounters, conditions, observations, collect(DISTINCT m) AS medications

    OPTIONAL MATCH (p)<-[:HAS_SUBJECT|DURING_ENCOUNTER*1..2]-(pr:Procedure)
    WITH p, encounters, conditions, observations, medications, collect(DISTINCT pr) AS procedures

    WITH
    [item IN encounters | {type: 'Encounter', id: item.id, display_name: item.class_code, code: null, date: coalesce(item.start, ''), encounter_id: item.id, status: item.status}] +
    [item IN conditions | {type: 'Condition', id: item.id, display_name: item.display_name, code: item.code, date: coalesce(item.onset, ''), encounter_id: null, status: null}] +
    [item IN observations | {type: 'Observation', id: item.id, display_name: item.display_name, code: item.code, date: coalesce(item.effective, ''), encounter_id: null, value: item.value, unit: item.unit}] +
    [item IN medications | {type: 'MedicationRequest', id: item.id, display_name: item.display_name, code: item.code, date: coalesce(item.authoredOn, ''), encounter_id: null, status: item.status}] +
    [item IN procedures | {type: 'Procedure', id: item.id, display_name: item.display_name, code: item.code, date: coalesce(item.performed, ''), encounter_id: null, status: null}] AS allEvents

    UNWIND allEvents AS ev
    RETURN ev
    ORDER BY ev.date ASC
    LIMIT 500
    """

    result = await session.run(query, {"id": patient_fhir_id}, timeout=QUERY_TIMEOUT_SECONDS)
    events = [record["ev"] async for record in result]

    return {"patient_id": patient_fhir_id, "events": events, "count": len(events)}
