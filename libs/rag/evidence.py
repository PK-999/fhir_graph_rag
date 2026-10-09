"""Format retrieved facts into exact source citations and bounded answers."""

from typing import Any

from libs.rag.claims import summary_fields
from libs.rag.plans import QueryPlan


def build_response(
    plan: QueryPlan,
    rows: list[dict[str, Any]],
    planner: str,
    cypher: str,
    parameters: dict[str, Any],
    *,
    offset: int = 0,
    has_more: bool = False,
) -> dict[str, Any]:
    """Clinical text uses only observed result fields, with every fact inspectable."""
    evidence: dict[str, dict[str, Any]] = {}

    def cite(
        resource_id: str | None,
        patient_id: str,
        label: str,
        facts: dict[str, Any],
        raw_reference: Any = None,
    ) -> None:
        if not resource_id:
            return
        resource_type = resource_id.split("/", 1)[0]
        if resource_type != "Patient":
            association = "patient" if resource_type == "AllergyIntolerance" else "subject"
            facts[f"{resource_type}.{association}.reference"] = raw_reference
        evidence[resource_id] = {
            "type": resource_type,
            "id": resource_id,
            "patient_id": patient_id,
            "label": label,
            "source_url": f"/resources/{resource_id}",
            "facts": {key: value for key, value in facts.items() if value is not None},
        }

    for row in rows:
        patient_id = row["patient_id"]
        cite(
            patient_id,
            patient_id,
            row.get("name", patient_id),
            {
                "Patient.name[0].given[0]": row.get("given"),
                "Patient.name[0].family": row.get("family"),
            },
        )
        cite(
            row.get("condition_id"),
            patient_id,
            row.get("condition_name") or "Condition",
            {
                "Condition.code.coding[0].code": row.get("condition_code"),
                "Condition.code.coding[0].display": row.get("condition_name"),
            },
            row.get("_condition_subject_reference", patient_id),
        )
        cite(
            row.get("observation_id"),
            patient_id,
            row.get("lab_name") or "Latest recorded lab",
            {
                "Observation.code.coding[0].code": row.get("lab_code"),
                "Observation.code.coding[0].display": row.get("lab_name"),
                "Observation.status": row.get("lab_status"),
                "Observation.valueQuantity.value": row.get("value"),
                "Observation.valueQuantity.unit": row.get("unit"),
                "Observation.effectiveDateTime": row.get("observed_at"),
            },
            row.get("_observation_subject_reference", patient_id),
        )
        cite(
            row.get("medication_id"),
            patient_id,
            "Recorded medication request",
            {
                "MedicationRequest.medicationCodeableConcept.coding[0].code": row.get(
                    "medication_code"
                ),
                "MedicationRequest.medicationCodeableConcept.coding[0].display": row.get(
                    "medication_name"
                ),
                "MedicationRequest.status": row.get("medication_status"),
                "MedicationRequest.authoredOn": row.get("authored_on"),
            },
            row.get("_medication_subject_reference", patient_id),
        )
        if row.get("resource_id"):
            kind = row["resource_type"]
            facts = {
                f"{kind}.code.coding[0].code": row.get("code"),
                f"{kind}.code.coding[0].display": row.get("_resource_code_display"),
                f"{kind}.type[0].coding[0].display": row.get("_resource_type_display"),
                f"{kind}.status": row.get("status"),
            }
            if kind == "Observation":
                facts.update(
                    {
                        "Observation.valueQuantity.value": row.get("value"),
                        "Observation.valueQuantity.unit": row.get("unit"),
                        "Observation.effectiveDateTime": row.get("observed_at"),
                    }
                )
            if kind == "MedicationRequest":
                facts["MedicationRequest.medicationCodeableConcept.coding[0].code"] = row.get(
                    "medication_code"
                )
                facts["MedicationRequest.medicationCodeableConcept.coding[0].display"] = row.get(
                    "_resource_medication_display"
                )
            if row.get("event_field") and row.get("event_at") is not None:
                facts[row["event_field"]] = row["event_at"]
            association_column = (
                "_resource_patient_reference"
                if kind == "AllergyIntolerance"
                else "_resource_subject_reference"
            )
            cite(
                row["resource_id"],
                patient_id,
                row.get("display") or kind,
                facts,
                row.get(association_column, patient_id),
            )

    answer = (
        "No matching result rows were found for these criteria. This does not establish the absence of a condition."
        if not rows
        else f"Retrieved {len(rows)} result rows (limited to {plan.limit}); this is not a total population count."
    )
    if rows and plan.intent == "latest_lab_medication":
        answer += " Each patient has a latest recorded qualifying lab result and a MedicationRequest marked active. Active status does not establish adherence."
    if rows and plan.intent == "medication_cohort":
        answer += " Each patient has a MedicationRequest marked active. Active status does not establish adherence."
    if rows and plan.intent == "patient_lab_history":
        answer += " Lab history includes final, amended, and corrected recorded Observations, ordered by recorded dates; undated results follow dated results."
    if rows and plan.intent == "patient_history":
        answer += " History is ordered by recorded dates; undated entries follow dated entries."
    if rows:
        answer += " More results are available." if has_more else " End of this result set."
    return {
        "status": "answered",
        "answer": answer,
        "results": [
            {key: value for key, value in row.items() if not key.startswith("_")} for row in rows
        ],
        "result_count": len(rows),
        "evidence": list(evidence.values()),
        "plan": plan.model_dump(exclude_none=True),
        "planner": planner,
        "cypher": cypher,
        "parameters": parameters,
        "pagination": {
            "offset": offset,
            "limit": plan.limit,
            "has_more": has_more,
            "next_offset": offset + plan.limit if has_more else None,
        },
        **summary_fields(),
    }


def abstain(reason: str) -> dict[str, Any]:
    """Unsupported questions do not cause retrieval or fabricate evidence."""
    return {
        "status": "abstained",
        "answer": reason,
        "results": [],
        "result_count": 0,
        "evidence": [],
        "plan": None,
        "planner": "unsupported",
        "cypher": None,
        "parameters": {},
        "pagination": None,
        **summary_fields(),
    }
