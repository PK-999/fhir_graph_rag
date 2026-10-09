"""Assistant executes owned templates and returns exact resource evidence."""

import json
from collections.abc import AsyncIterator
from typing import Any, cast

import httpx
import pytest
from apps.api.app.config import settings
from apps.api.app.routers import assistant
from neo4j import Query
from openai import AsyncOpenAI
from pydantic import ValidationError

from libs.rag.plans import QueryPlan


class Session:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.query: Query | None = None
        self.parameters: dict[str, Any] = {}

    async def run(self, query: Query, parameters: dict[str, Any]) -> Any:
        self.query, self.parameters = query, parameters

        async def records() -> AsyncIterator[Any]:
            for row in self.rows:
                yield type("Record", (), {"data": lambda self, row=row: row})()

        return records()


@pytest.mark.parametrize("offset, returned, has_more", [(0, 3, True), (2, 2, False), (4, 0, False)])
async def test_pages_exclude_lookahead_from_results_and_citations(
    offset: int, returned: int, has_more: bool
) -> None:
    rows = [{"patient_id": f"Patient/p-{offset + i}", "name": "Patient"} for i in range(returned)]
    session = Session(rows)
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(
            query="List patients", plan=QueryPlan(intent="patient_list", limit=2), offset=offset
        ),
        session,
    )
    assert response["results"] == rows[:2]
    assert response["result_count"] == min(2, returned)
    assert [item["id"] for item in response["evidence"]] == [row["patient_id"] for row in rows[:2]]
    assert response["pagination"] == {
        "offset": offset,
        "limit": 2,
        "has_more": has_more,
        "next_offset": offset + 2 if has_more else None,
    }
    assert session.parameters["offset"] == offset
    assert session.parameters["fetch_limit"] == 3


@pytest.mark.parametrize("offset", [-1, True, 1.5, "2", 2**63])
def test_invalid_page_offsets_are_rejected(offset: Any) -> None:
    with pytest.raises(ValidationError):
        assistant.AssistantQuery(query="List patients", offset=offset)


async def test_history_page_reuses_explicit_plan_and_cites_only_returned_records() -> None:
    rows = [
        {
            "patient_id": "Patient/p",
            "resource_id": f"Encounter/e-{i}",
            "resource_type": "Encounter",
            "status": "finished",
        }
        for i in range(3)
    ]
    session = Session(rows)
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(
            query="Show history for Patient/p",
            plan=QueryPlan(intent="patient_history", patient_id="Patient/p", limit=2),
            offset=2,
        ),
        session,
    )
    assert response["planner"] == "explicit"
    assert [item["id"] for item in response["evidence"]] == [
        "Patient/p",
        "Encounter/e-0",
        "Encounter/e-1",
    ]
    assert response["pagination"]["next_offset"] == 4


@pytest.mark.parametrize("count", [0, 2])
async def test_supported_question_needs_no_model_and_returns_source_evidence(
    count: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_model() -> None:
        pytest.fail("Supported questions do not need a model call")

    monkeypatch.setattr(assistant, "get_llm_client", forbidden_model)
    rows = [
        {
            "patient_id": f"Patient/p-{i}",
            "name": "Test Patient",
            "given": "Test",
            "family": "Patient",
        }
        for i in range(count)
    ]
    session = Session(rows)
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(query="List five patients"), session
    )
    assert response["result_count"] == count
    assert response["results"] == rows
    assert [item["id"] for item in response["evidence"]] == [row["patient_id"] for row in rows]
    assert session.parameters["limit"] == 5
    assert isinstance(session.query, Query)
    assert session.query.timeout == 30


async def test_unsupported_question_never_executes_graph() -> None:
    session = Session([])
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(query="Recommend treatment for these patients"), session
    )
    assert response["status"] == "abstained"
    assert response["evidence"] == []
    assert session.query is None


@pytest.mark.parametrize(
    "content", ['{"intent":"patient_list","cypher":"DELETE n"}', "not json", '{"unsupported":true}']
)
async def test_invalid_model_plan_abstains_and_closes_client(
    content: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def model_response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "local",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    client = AsyncOpenAI(
        api_key="local-test",
        base_url="http://local.invalid/v1",
        http_client=cast("Any", httpx.AsyncClient(transport=httpx.MockTransport(model_response))),
    )
    monkeypatch.setattr(assistant, "get_llm_client", lambda: client)
    session = Session([])
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(query="List five patients", use_model=True), session
    )
    assert response["status"] == "abstained"
    assert session.query is None
    assert client.is_closed()


async def test_model_code_namespaces_are_normalized_before_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = '{"intent":"latest_lab_medication","lab_code":"LOINC:4548-4","medication_code":"RxNorm:6809","threshold":8,"unit":"%"}'

    def response(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "local",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    client = AsyncOpenAI(
        api_key="local-test",
        base_url="http://local.invalid/v1",
        http_client=cast("Any", httpx.AsyncClient(transport=httpx.MockTransport(response))),
    )
    monkeypatch.setattr(assistant, "get_llm_client", lambda: client)
    session = Session([])
    await assistant.ask_assistant(
        assistant.AssistantQuery(
            query="Find patients whose latest HbA1c is above 8% with active Metformin",
            use_model=True,
        ),
        session,
    )
    assert session.parameters["lab_code"] == "4548-4"
    assert session.parameters["medication_code"] == "6809"
    assert client.is_closed()


def local_client(content: str, *, fail: bool = False) -> AsyncOpenAI:
    def response(request: httpx.Request) -> httpx.Response:
        if fail:
            return httpx.Response(503, json={"error": {"message": "unavailable"}})
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "local",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    return AsyncOpenAI(
        api_key="local-test",
        base_url="http://local.invalid/v1",
        max_retries=0,
        http_client=cast("Any", httpx.AsyncClient(transport=httpx.MockTransport(response))),
    )


def lab_row(identifier: str = "o") -> dict[str, Any]:
    return {
        "patient_id": "Patient/p",
        "observation_id": f"Observation/{identifier}",
        "lab_code": "4548-4",
        "lab_status": "final",
        "value": 9.2,
        "unit": "%",
        "observed_at": "2025-02-01T12:00:00Z",
    }


async def test_opt_in_summary_renders_only_validated_source_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claims = [
        {"evidence_id": "Observation/o", "field": "Observation.valueQuantity.value", "value": 9.2},
        {
            "evidence_id": "Observation/o",
            "field": "Observation.effectiveDateTime",
            "value": "2025-02-01T12:00:00Z",
        },
    ]
    client = local_client(json.dumps({"claims": claims}))
    monkeypatch.setattr(assistant, "get_llm_client", lambda: client)
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(query="Show HbA1c history for Patient/p", use_summary_model=True),
        Session([lab_row()]),
    )
    assert response["claims"] == claims
    assert (
        response["summary"]
        == 'Observation/o: Observation.valueQuantity.value = 9.2.\nObservation/o: Observation.effectiveDateTime = "2025-02-01T12:00:00Z".'
    )
    assert response["summary_metadata"] == {
        "requested": True,
        "status": "validated",
        "model": settings.llm_model,
        "claim_count": 2,
    }
    assert response["status"] == "answered"
    assert client.is_closed()


@pytest.mark.parametrize(
    "content",
    [
        '{"claims":[{"evidence_id":"Observation/invented","field":"Observation.valueQuantity.value","value":9.2}]}',
        '{"claims":[{"evidence_id":"Observation/o","field":"Observation.diagnosis","value":"diabetes"}]}',
        '{"claims":[{"evidence_id":"Observation/o","field":"Observation.valueQuantity.value","value":99}]}',
        '{"claims":[{"evidence_id":"Observation/o","field":"Observation.valueQuantity.value","value":"9.2"}]}',
        '{"claims":[{"evidence_id":"Observation/o","field":"Observation.valueQuantity.value","value":true}]}',
        '{"claims":[{"evidence_id":"Observation/o","field":"Observation.valueQuantity.value","value":NaN}]}',
        '{"claims":[{"evidence_id":"Observation/o","field":"Observation.valueQuantity.value","value":9.2,"text":"Start insulin"}]}',
        '{"claims":[],"summary":"Start insulin"}',
        '{"claims":[]}',
        "not JSON",
        '{"claims":[{"evidence_id":"Observation/o","field":"Observation.valueQuantity.value","value":9.2},{"evidence_id":"Observation/o","field":"Observation.valueQuantity.value","value":9.2}]}',
    ],
)
async def test_invented_or_unstructured_summary_is_rejected_without_losing_retrieval(
    content: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = local_client(content)
    monkeypatch.setattr(assistant, "get_llm_client", lambda: client)
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(query="Show HbA1c history for Patient/p", use_summary_model=True),
        Session([lab_row()]),
    )
    assert response["summary_metadata"]["status"] == "rejected"
    assert response["claims"] == [] and response["summary"] is None
    assert response["results"] == [lab_row()] and response["status"] == "answered"
    assert "insulin" not in response["answer"].lower()
    assert client.is_closed()


async def test_summary_cannot_cite_the_lookahead_row(monkeypatch: pytest.MonkeyPatch) -> None:
    client = local_client(
        '{"claims":[{"evidence_id":"Observation/lookahead","field":"Observation.valueQuantity.value","value":9.2}]}'
    )
    monkeypatch.setattr(assistant, "get_llm_client", lambda: client)
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(
            query="Show HbA1c history for Patient/p",
            use_summary_model=True,
            plan=QueryPlan(
                intent="patient_lab_history", patient_id="Patient/p", lab_code="4548-4", limit=1
            ),
        ),
        Session([lab_row(), lab_row("lookahead")]),
    )
    assert response["summary_metadata"]["status"] == "rejected"
    assert response["pagination"]["has_more"] is True
    assert "Observation/lookahead" not in {item["id"] for item in response["evidence"]}


@pytest.mark.parametrize(
    "question,rows,expected",
    [
        ("Show HbA1c history for Patient/p", [], "no_evidence"),
        ("Show HbA1c history for Patient/p since yesterday", [], "no_evidence"),
    ],
)
async def test_empty_or_unsupported_retrieval_never_calls_summary_model(
    question: str, rows: list[dict[str, Any]], expected: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        assistant, "get_llm_client", lambda: pytest.fail("No evidence cannot be summarized")
    )
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(query=question, use_summary_model=True), Session(rows)
    )
    assert response["summary_metadata"]["status"] == expected
    assert response["summary"] is None and response["claims"] == []


async def test_summary_provider_failure_preserves_grounded_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = local_client("", fail=True)
    monkeypatch.setattr(assistant, "get_llm_client", lambda: client)
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(query="Show HbA1c history for Patient/p", use_summary_model=True),
        Session([lab_row()]),
    )
    assert response["summary_metadata"]["status"] == "unavailable"
    assert response["summary"] is None and response["results"] == [lab_row()]
    assert client.is_closed()


async def test_summary_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assistant, "get_llm_client", lambda: pytest.fail("Model is opt-in"))
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(query="Show HbA1c history for Patient/p"), Session([lab_row()])
    )
    assert response["summary_metadata"] == {
        "requested": False,
        "status": "not_requested",
        "model": None,
        "claim_count": 0,
    }
    assert response["summary"] is None and response["claims"] == []


async def test_model_plan_cannot_drop_an_unsupported_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = local_client('{"intent":"medication_cohort","medication_code":"6809"}')
    monkeypatch.setattr(assistant, "get_llm_client", lambda: client)
    session = Session([])
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(
            query="Which patients have active Metformin prescriptions who are over 65?",
            use_model=True,
        ),
        session,
    )
    assert response["status"] == "abstained"
    assert session.query is None
    await client.close()


async def test_supported_model_plan_disagreement_abstains(monkeypatch: pytest.MonkeyPatch) -> None:
    client = local_client('{"intent":"patient_list","limit":20}')
    monkeypatch.setattr(assistant, "get_llm_client", lambda: client)
    session = Session([])
    response = await assistant.ask_assistant(
        assistant.AssistantQuery(query="List five patients", use_model=True), session
    )
    assert response["status"] == "abstained"
    assert session.query is None and client.is_closed()
