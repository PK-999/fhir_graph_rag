"""Application-owned parameterized clinical retrieval templates."""

from typing import Any

from libs.rag.plans import QueryPlan

PATIENT_FIELDS = "p.id AS patient_id, p.name_0_given_0 AS given, p.name_0_family AS family, coalesce(p.name_0_given_0,'') + ' ' + coalesce(p.name_0_family,'') AS name"


def compile_plan(plan: QueryPlan, *, offset: int = 0) -> tuple[str, dict[str, Any]]:
    """Return a fixed query plus data parameters; model text never becomes Cypher."""
    params = plan.model_dump(exclude_none=True, exclude={"intent", "comparison"})
    params.update(offset=offset, fetch_limit=plan.limit + 1)
    if plan.intent == "patient_list":
        query = f"MATCH (p:Patient) RETURN {PATIENT_FIELDS} ORDER BY patient_id SKIP $offset LIMIT $fetch_limit"
    elif plan.intent == "condition_cohort":
        query = f"""
        MATCH (c:Condition)-[:SUBJECT]->(p:Patient)
        WHERE c.code_coding_0_code = $condition_code
        WITH p, c ORDER BY c.id
        WITH p, head(collect(c)) AS c
        RETURN {PATIENT_FIELDS}, c.id AS condition_id,
               c.subject_reference AS _condition_subject_reference,
               c.code_coding_0_code AS condition_code, c.code_coding_0_display AS condition_name
        ORDER BY patient_id SKIP $offset LIMIT $fetch_limit
        """
    elif plan.intent == "latest_lab_medication":
        operator = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[plan.comparison]
        condition_match = ""
        condition_fields = ""
        if plan.condition_code:
            condition_match = """MATCH (c:Condition)-[:SUBJECT]->(p)
                WHERE c.code_coding_0_code = $condition_code
                WITH p, o, m, c ORDER BY c.id
                WITH p, o, m, head(collect(c)) AS c"""
            condition_fields = ", c.id AS condition_id, c.subject_reference AS _condition_subject_reference, c.code_coding_0_code AS condition_code, c.code_coding_0_display AS condition_name"
        query = f"""
        MATCH (o:Observation)-[:SUBJECT]->(p:Patient)
        WHERE o.code_coding_0_code = $lab_code
          AND o.status IN ['final', 'amended', 'corrected'] AND o.effective_date_time IS NOT NULL
        WITH p, o ORDER BY datetime(o.effective_date_time).epochSeconds DESC, datetime(o.effective_date_time).nanosecond DESC, o.id DESC
        WITH p, head(collect(o)) AS o
        WHERE o.value_quantity_value {operator} $threshold
          AND o.value_quantity_value = toFloatOrNull(o.value_quantity_value)
          AND o.value_quantity_unit = $unit
        MATCH (m:MedicationRequest)-[:SUBJECT]->(p)
        WHERE m.medication_codeable_concept_coding_0_code = $medication_code AND m.status = 'active'
        WITH p, o, m ORDER BY m.id
        WITH p, o, head(collect(m)) AS m
        {condition_match}
        RETURN {PATIENT_FIELDS}, o.id AS observation_id, o.code_coding_0_code AS lab_code, o.code_coding_0_display AS lab_name, o.status AS lab_status,
               o.subject_reference AS _observation_subject_reference, m.subject_reference AS _medication_subject_reference,
               o.value_quantity_value AS value, o.value_quantity_unit AS unit,
               o.effective_date_time AS observed_at, m.id AS medication_id,
               m.medication_codeable_concept_coding_0_code AS medication_code,
               m.status AS medication_status {condition_fields}
        ORDER BY patient_id SKIP $offset LIMIT $fetch_limit
        """
    elif plan.intent == "medication_cohort":
        condition_match = ""
        condition_fields = ""
        if plan.condition_code:
            condition_match = """MATCH (c:Condition)-[:SUBJECT]->(p)
                WHERE c.code_coding_0_code = $condition_code
                WITH p, m, c ORDER BY c.id
                WITH p, m, head(collect(c)) AS c"""
            condition_fields = ", c.id AS condition_id, c.subject_reference AS _condition_subject_reference, c.code_coding_0_code AS condition_code, c.code_coding_0_display AS condition_name"
        query = f"""
        MATCH (m:MedicationRequest)-[:SUBJECT]->(p:Patient)
        WHERE m.medication_codeable_concept_coding_0_code = $medication_code AND m.status = 'active'
        WITH p, m ORDER BY m.id
        WITH p, head(collect(m)) AS m
        {condition_match}
        RETURN {PATIENT_FIELDS}, m.id AS medication_id,
               m.subject_reference AS _medication_subject_reference,
               m.medication_codeable_concept_coding_0_code AS medication_code,
               m.medication_codeable_concept_coding_0_display AS medication_name,
               m.status AS medication_status, m.authored_on AS authored_on {condition_fields}
        ORDER BY patient_id SKIP $offset LIMIT $fetch_limit
        """
    elif plan.intent == "patient_lab_history":
        lab_filter = "AND o.code_coding_0_code = $lab_code" if plan.lab_code else ""
        query = f"""
        MATCH (o:Observation)-[:SUBJECT]->(p:Patient)
        WHERE p.id = $patient_id AND o.status IN ['final', 'amended', 'corrected']
              {lab_filter}
        RETURN {PATIENT_FIELDS}, o.id AS observation_id,
               o.subject_reference AS _observation_subject_reference,
               o.code_coding_0_code AS lab_code, o.code_coding_0_display AS lab_name,
               o.status AS lab_status, o.value_quantity_value AS value,
               o.value_quantity_unit AS unit, o.effective_date_time AS observed_at
        ORDER BY observed_at IS NULL ASC, datetime(observed_at).epochSeconds DESC,
                 datetime(observed_at).nanosecond DESC, observation_id ASC
        SKIP $offset LIMIT $fetch_limit
        """
    else:
        query = f"""
        MATCH (p:Patient) WHERE p.id = $patient_id
        OPTIONAL MATCH (r)-[:SUBJECT|PATIENT]->(p)
        WHERE (r:AllergyIntolerance AND coalesce(r.patient_reference_canonical, r.patient_reference) = p.id)
           OR (NOT r:AllergyIntolerance AND coalesce(r.subject_reference_canonical, r.subject_reference) = p.id)
        WITH DISTINCT p, r,
             CASE
               WHEN r:Observation OR r:DiagnosticReport THEN r.effective_date_time
               WHEN r:Encounter THEN r.period_start
               WHEN r:Condition THEN coalesce(r.onset_date_time, r.recorded_date)
               WHEN r:MedicationRequest OR r:ServiceRequest THEN r.authored_on
               WHEN r:Procedure THEN r.performed_date_time
               WHEN r:AllergyIntolerance THEN r.recorded_date
             END AS event_at,
             CASE
               WHEN r:Observation THEN 'Observation.effectiveDateTime'
               WHEN r:DiagnosticReport THEN 'DiagnosticReport.effectiveDateTime'
               WHEN r:Encounter THEN 'Encounter.period.start'
               WHEN r:Condition AND r.onset_date_time IS NOT NULL THEN 'Condition.onsetDateTime'
               WHEN r:Condition THEN 'Condition.recordedDate'
               WHEN r:MedicationRequest THEN 'MedicationRequest.authoredOn'
               WHEN r:ServiceRequest THEN 'ServiceRequest.authoredOn'
               WHEN r:Procedure THEN 'Procedure.performedDateTime'
               WHEN r:AllergyIntolerance THEN 'AllergyIntolerance.recordedDate'
             END AS event_field
        RETURN {PATIENT_FIELDS}, r.id AS resource_id, labels(r)[0] AS resource_type,
               r.subject_reference AS _resource_subject_reference, r.patient_reference AS _resource_patient_reference,
               r.code_coding_0_display AS _resource_code_display,
               r.medication_codeable_concept_coding_0_display AS _resource_medication_display,
               r.type_0_coding_0_display AS _resource_type_display,
               r.code_coding_0_code AS code,
               coalesce(r.code_coding_0_display, r.medication_codeable_concept_coding_0_display, r.type_0_coding_0_display, labels(r)[0]) AS display,
               r.value_quantity_value AS value, r.value_quantity_unit AS unit,
               r.effective_date_time AS observed_at, r.status AS status,
               r.medication_codeable_concept_coding_0_code AS medication_code,
               event_at, event_field
        ORDER BY event_at IS NULL ASC, datetime(event_at).epochSeconds DESC, datetime(event_at).nanosecond DESC, resource_id ASC SKIP $offset LIMIT $fetch_limit
        """
    return query.strip(), params
