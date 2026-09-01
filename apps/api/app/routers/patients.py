"""Patient API router."""

from typing import Any

from apps.api.app.dependencies import db
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/patients")


async def get_neo4j_session():
    if not db.neo4j_driver:
        raise HTTPException(status_code=503, detail="Neo4j not connected")
    async with db.neo4j_driver.session() as session:
        yield session


@router.get("")
async def search_patients(
    q: str | None = None,
    gender: str | None = None,
    dob_start: str | None = None,
    dob_end: str | None = None,
    limit: int = Query(default=20, le=100),
    page: int = Query(default=1, ge=1),
    sort: str = Query(default="name"),
    order: str = Query(default="asc"),
    session=Depends(get_neo4j_session)
) -> dict[str, Any]:
    """Search patients by name."""
    offset = (page - 1) * limit

    valid_sort = {"id": "p.id", "name": "p.display_name", "gender": "p.gender", "birthDate": "p.birthDate"}
    sort_field = valid_sort.get(sort, "p.display_name")
    sort_order = "DESC" if order.lower() == "desc" else "ASC"
    order_clause = f"ORDER BY {sort_field} {sort_order}"

    where_clauses = []
    params = {"limit": limit, "offset": offset}

    if q:
        where_clauses.append("(toLower(p.display_name) CONTAINS toLower($q) OR p.id CONTAINS $q)")
        params["q"] = q
    if gender:
        where_clauses.append("toLower(p.gender) = toLower($gender)")
        params["gender"] = gender
    if dob_start:
        where_clauses.append("p.birthDate >= $dob_start")
        params["dob_start"] = dob_start
    if dob_end:
        where_clauses.append("p.birthDate <= $dob_end")
        params["dob_end"] = dob_end

    where_str = ""
    if where_clauses:
        where_str = "WHERE " + " AND ".join(where_clauses)

    count_query = f"""
    MATCH (p:Patient)
    {where_str}
    RETURN count(p) AS total
    """
    
    query = f"""
    MATCH (p:Patient)
    {where_str}
    RETURN p.id AS id, p.display_name AS name, p.gender AS gender, p.birthDate AS birthDate
    {order_clause}
    SKIP $offset LIMIT $limit
    """

    count_result = await session.run(count_query, params)
    count_record = await count_result.single()
    total = count_record["total"] if count_record else 0

    result = await session.run(query, params)
    patients = [record.data() async for record in result]
    
    return {
        "data": patients,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit
        }
    }


@router.get("/{patient_id}")
async def get_patient_detail(patient_id: str, session=Depends(get_neo4j_session)) -> dict[str, Any]:
    """Get full Patient 360 details with resource counts."""
    query = """
    MATCH (p:Patient {id: $id})
    OPTIONAL MATCH (p)<-[:HAS_SUBJECT]-(e:Encounter)
    WITH p, collect(DISTINCT e) as all_encounters
    WITH p, all_encounters, size(all_encounters) AS encounter_count,
         [e IN all_encounters | e{.*}][0..10] AS encounters

    OPTIONAL MATCH (p)<-[:HAS_SUBJECT|DURING_ENCOUNTER*1..2]-(c:Condition)
    WITH p, encounters, encounter_count, collect(DISTINCT c) AS all_conditions
    WITH p, encounters, encounter_count,
         size(all_conditions) AS condition_count,
         [c IN all_conditions | c{.*}][0..10] AS conditions

    OPTIONAL MATCH (p)<-[:HAS_SUBJECT|DURING_ENCOUNTER*1..2]-(m:MedicationRequest)
    WITH p, encounters, encounter_count, conditions, condition_count,
         collect(DISTINCT m) AS all_medications
    WITH p, encounters, encounter_count, conditions, condition_count,
         size(all_medications) AS medication_count,
         [m IN all_medications | m{.*}][0..10] AS medications

    OPTIONAL MATCH (p)<-[:HAS_SUBJECT|DURING_ENCOUNTER*1..2]-(o:Observation)
    WITH p, encounters, encounter_count, conditions, condition_count,
         medications, medication_count, collect(DISTINCT o) AS all_observations
    WITH p, encounters, encounter_count, conditions, condition_count,
         medications, medication_count,
         size(all_observations) AS observation_count,
         [o IN all_observations | o{.*}][0..10] AS observations

    OPTIONAL MATCH (p)<-[:HAS_SUBJECT|DURING_ENCOUNTER*1..2]-(pr:Procedure)
    WITH p, encounters, encounter_count, conditions, condition_count,
         medications, medication_count, observations, observation_count,
         collect(DISTINCT pr) AS all_procedures
    WITH p, encounters, encounter_count, conditions, condition_count,
         medications, medication_count, observations, observation_count,
         size(all_procedures) AS procedure_count,
         [pr IN all_procedures | pr{.*}][0..10] AS procedures

    RETURN p.id AS id, p.display_name AS name, p.gender AS gender,
           p.birthDate AS birthDate,
           encounters, encounter_count,
           conditions, condition_count,
           medications, medication_count,
           observations, observation_count,
           procedures, procedure_count
    """
    result = await session.run(query, {"id": f"Patient/{patient_id}"})
    record = await result.single()

    if not record:
        raise HTTPException(status_code=404, detail="Patient not found")

    data = record.data()
    # Add a convenience counts object for the frontend
    data["counts"] = {
        "encounters": data.get("encounter_count", 0),
        "conditions": data.get("condition_count", 0),
        "medications": data.get("medication_count", 0),
        "observations": data.get("observation_count", 0),
        "procedures": data.get("procedure_count", 0),
    }
    return data

@router.get("/{patient_id}/summary-graph")
async def get_patient_summary_graph(patient_id: str, session=Depends(get_neo4j_session)) -> dict[str, Any]:
    """Get Patient 360 summary graph with bundled resource counts."""
    query = """
    MATCH (p:Patient {id: $id})
    
    // Group all connected nodes by their primary label
    OPTIONAL MATCH (p)-[r]-(n)
    WITH p, head(labels(n)) AS nodeType, count(n) AS count
    WHERE nodeType IS NOT NULL AND nodeType <> 'Patient'
    
    RETURN p.id AS patientId, p.display_name AS patientName, 
           p.gender AS gender, p.birthDate AS birthDate,
           collect({type: nodeType, count: count}) AS bundles
    """
    
    result = await session.run(query, {"id": f"Patient/{patient_id}"})
    record = await result.single()
    
    if not record:
        raise HTTPException(status_code=404, detail="Patient not found")
        
    patient_id_full = record["patientId"]
    patient_node = {
        "id": patient_id_full,
        "labels": ["Patient"],
        "properties": {
            "display_name": record["patientName"],
            "gender": record["gender"],
            "birthDate": record["birthDate"]
        }
    }
    
    nodes = [patient_node]
    edges = []
    
    for bundle in record["bundles"]:
        b_type = bundle["type"]
        b_count = bundle["count"]
        if b_type is None: continue
        
        bundle_id = f"Summary/{b_type}"
        nodes.append({
            "id": bundle_id,
            "labels": ["SummaryNode"],
            "properties": {
                "display_name": f"{b_type}s ({b_count})",
                "count": b_count,
                "originalType": b_type
            }
        })
        edges.append({
            "id": f"e-{patient_id_full}-{bundle_id}",
            "source": patient_id_full,
            "target": bundle_id,
            "type": f"HAS_{b_type.upper()}",
            "properties": {}
        })
        
    return {
        "nodes": nodes,
        "edges": edges,
        "truncated": False
    }
