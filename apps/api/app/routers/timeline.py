"""Timeline API router — chronological clinical events for a patient."""

from typing import Any

from apps.api.app.dependencies import get_neo4j_session
from fastapi import APIRouter, Depends
from neo4j import Query

router = APIRouter(prefix="/patients")

QUERY_TIMEOUT_SECONDS = 30


@router.get("/{patient_id}/timeline")
@router.get("/Patient/{patient_id}/timeline")
async def get_patient_timeline(
    patient_id: str,
    session: Any = Depends(get_neo4j_session),
) -> dict[str, Any]:
    """Return all clinical events for a patient ordered by date.

    Each event includes its type, display name, code, date, and
    the encounter it belongs to (if any).
    """
    patient_fhir_id = patient_id if patient_id.startswith("Patient/") else f"Patient/{patient_id}"

    query = """
    MATCH (p:Patient {id: $id})

    // Encounters (anchor events)
    OPTIONAL MATCH (p)<-[:SUBJECT]-(e:Encounter)
    WITH p, collect(DISTINCT e) AS encounters

    // Resources linked to patient directly or via encounter
    OPTIONAL MATCH (p)<-[:SUBJECT|ENCOUNTER*1..2]-(c:Condition)
    WITH p, encounters, collect(DISTINCT c) AS conditions

    OPTIONAL MATCH (p)<-[:SUBJECT|ENCOUNTER*1..2]-(o:Observation)
    WITH p, encounters, conditions, collect(DISTINCT o) AS observations

    OPTIONAL MATCH (p)<-[:SUBJECT|ENCOUNTER*1..2]-(m:MedicationRequest)
    WITH p, encounters, conditions, observations, collect(DISTINCT m) AS medications

    OPTIONAL MATCH (p)<-[:SUBJECT|ENCOUNTER*1..2]-(pr:Procedure)
    WITH p, encounters, conditions, observations, medications, collect(DISTINCT pr) AS procedures

    WITH
    [item IN encounters | {type: 'Encounter', id: item.id,
      display_name: coalesce(item.class_display, item.class__display, item.class_code, item.class__code),
      code: coalesce(item.class_code, item.class__code), date: coalesce(item.period_start, ''),
      encounter_id: item.id, status: item.status}] +
    [item IN conditions | {type: 'Condition', id: item.id,
      display_name: coalesce(item.code_coding_0_display, item.code_text), code: item.code_coding_0_code,
      date: coalesce(item.onset_date_time, item.recorded_date, ''),
      encounter_id: item.encounter_reference, status: item.clinical_status_coding_0_code}] +
    [item IN observations | {type: 'Observation', id: item.id,
      display_name: coalesce(item.code_coding_0_display, item.code_text), code: item.code_coding_0_code,
      date: coalesce(item.effective_date_time, item.effective_period_start, ''),
      encounter_id: item.encounter_reference, value: item.value_quantity_value,
      unit: item.value_quantity_unit, status: item.status}] +
    [item IN medications | {type: 'MedicationRequest', id: item.id,
      display_name: coalesce(item.medication_codeable_concept_coding_0_display,
                             item.medication_codeable_concept_text),
      code: item.medication_codeable_concept_coding_0_code, date: coalesce(item.authored_on, ''),
      encounter_id: item.encounter_reference, status: item.status}] +
    [item IN procedures | {type: 'Procedure', id: item.id,
      display_name: coalesce(item.code_coding_0_display, item.code_text), code: item.code_coding_0_code,
      date: coalesce(item.performed_date_time, item.performed_period_start, ''),
      encounter_id: item.encounter_reference, status: item.status}] AS allEvents

    UNWIND allEvents AS ev
    RETURN ev
    ORDER BY ev.date ASC
    LIMIT 500
    """

    result = await session.run(Query(query, timeout=QUERY_TIMEOUT_SECONDS), {"id": patient_fhir_id})
    events = [record["ev"] async for record in result]

    return {"patient_id": patient_fhir_id, "events": events, "count": len(events)}
