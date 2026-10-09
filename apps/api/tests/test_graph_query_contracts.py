"""Exercise graph API contracts at the external Neo4j session boundary."""

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from apps.api.app.routers import cohorts, dashboard, graph, patients, timeline
from fastapi import FastAPI
from fastapi.testclient import TestClient
from neo4j import Query


class Record(dict[str, Any]):
    def data(self) -> dict[str, Any]:
        return dict(self)


class Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = [Record(row) for row in rows]

    async def single(self) -> Record | None:
        return self.rows[0] if self.rows else None

    def __aiter__(self) -> AsyncIterator[Record]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[Record]:
        for row in self.rows:
            yield row


class RecordingSession:
    """Replace only the external driver call; retain real route and model code."""

    def __init__(self) -> None:
        self.calls: list[tuple[str | Query, dict[str, Any], dict[str, Any]]] = []
        self.results: list[list[dict[str, Any]]] = []

    async def run(
        self, query: str | Query, parameters: dict[str, Any] | None = None, **kwargs: Any
    ) -> Result:
        self.calls.append((query, parameters or {}, kwargs))
        return Result(self.results.pop(0) if self.results else [])


@pytest.fixture
def api() -> Iterator[tuple[TestClient, RecordingSession]]:
    app = FastAPI()
    session = RecordingSession()

    async def override_session() -> AsyncIterator[RecordingSession]:
        yield session

    for module in (patients, timeline, cohorts, graph, dashboard):
        app.include_router(module.router, prefix="/api/v1")
        app.dependency_overrides[module.get_neo4j_session] = override_session
    with TestClient(app) as client:
        yield client, session


@pytest.mark.parametrize("field", ["conditions", "condition_codes"])
def test_cohort_accepts_both_condition_filter_names(
    api: tuple[TestClient, RecordingSession], field: str
) -> None:
    client, session = api
    session.results = [[{"id": "Patient/p-1", "name": "Ada Shah", "birthDate": "2000-02-29"}]]
    response = client.post("/api/v1/cohorts/query", json={field: ["44054006"]})

    assert response.status_code == 200
    assert session.calls[0][1]["conditions"] == ["44054006"]
    cypher = str(session.calls[0][0])
    assert "[:SUBJECT|ENCOUNTER*1..2]" in cypher
    assert "c.code_coding_0_code" in cypher
    assert "c.code_coding_0_display" in cypher
    assert "RETURN DISTINCT" in cypher
    assert response.json()["patients"][0]["birthDate"] == "2000-02-29"


@pytest.mark.parametrize("field", ["conditions", "condition_codes"])
@pytest.mark.parametrize("codes", [[" "], ["A" * 100], [f"code-{i}" for i in range(50)]])
def test_invalid_cohort_codes_do_not_reach_neo4j(
    api: tuple[TestClient, RecordingSession], field: str, codes: list[str]
) -> None:
    client, session = api
    response = client.post("/api/v1/cohorts/query", json={field: codes})
    assert response.status_code == 422
    assert session.calls == []


def test_cohort_combines_age_and_condition_predicates(
    api: tuple[TestClient, RecordingSession],
) -> None:
    client, session = api
    response = client.post(
        "/api/v1/cohorts/query", json={"conditions": ["44054006"], "min_age": 18, "max_age": 40}
    )
    assert response.status_code == 200
    cypher = str(session.calls[0][0])
    assert "WHERE any(" in cypher
    assert "AND duration.between(date(p.birth_date), date($today)).years >= $min_age" in cypher
    assert "AND duration.between(date(p.birth_date), date($today)).years <= $max_age" in cypher
    assert "WHERE p.birth" not in cypher
    assert session.calls[0][1]["min_age"] == 18
    assert session.calls[0][1]["max_age"] == 40
    assert len(session.calls[0][1]["today"]) == 10


def test_patient_search_reads_flattened_demographics(
    api: tuple[TestClient, RecordingSession],
) -> None:
    client, session = api
    session.results = [
        [{"total": 1}],
        [{"id": "Patient/p-1", "name": "Ada Shah", "birthDate": "2000-02-29"}],
    ]
    response = client.get("/api/v1/patients?q=Ada&dob_start=1990-01-01&sort=birthDate")
    assert response.status_code == 200
    cypher = str(session.calls[1][0])
    assert "p.name_0_given_0" in cypher
    assert "p.name_0_family" in cypher
    assert "p.birth_date AS birthDate" in cypher
    assert "ORDER BY p.birth_date ASC" in cypher
    assert "p.birthDate" not in cypher
    assert "p.display_name" not in cypher
    assert response.json()["pagination"]["total"] == 1


@pytest.mark.parametrize("patient_id", ["p-1", "Patient/p-1"])
def test_patient_detail_reads_real_relationships_and_preserves_ui_fields(
    api: tuple[TestClient, RecordingSession], patient_id: str
) -> None:
    client, session = api
    session.results = [[{"id": "Patient/p-1", "name": "Ada Shah", "encounter_count": 2}]]
    response = client.get(f"/api/v1/patients/{patient_id}")
    assert response.status_code == 200
    query, parameters, _ = session.calls[0]
    cypher = str(query)
    assert parameters["id"] == "Patient/p-1"
    assert "[:SUBJECT]" in cypher
    assert "[:SUBJECT|ENCOUNTER*1..2]" in cypher
    assert "start: e.period_start" in cypher
    assert "display_name: coalesce(c.code_coding_0_display, c.code_text)" in cypher
    assert "code: c.code_coding_0_code" in cypher
    assert "m.medication_codeable_concept_coding_0_display" in cypher
    assert "value: o.value_quantity_value" in cypher
    assert response.json()["counts"]["encounters"] == 2


@pytest.mark.parametrize("patient_id", ["p-1", "Patient/p-1"])
def test_timeline_reads_flattened_clinical_fields_and_encounter_links(
    api: tuple[TestClient, RecordingSession], patient_id: str
) -> None:
    client, session = api
    session.results = [
        [{"ev": {"id": "Observation/o-1", "encounter_id": "Encounter/e-1", "value": 0}}]
    ]
    response = client.get(f"/api/v1/patients/{patient_id}/timeline")
    assert response.status_code == 200
    query, parameters, _ = session.calls[0]
    cypher = str(query)
    assert parameters["id"] == "Patient/p-1"
    for field in (
        "period_start",
        "onset_date_time",
        "effective_date_time",
        "authored_on",
        "performed_date_time",
        "code_coding_0_display",
        "value_quantity_value",
        "value_quantity_unit",
        "medication_codeable_concept_coding_0_display",
        "encounter_reference",
    ):
        assert f"item.{field}" in cypher
    assert "HAS_SUBJECT" not in cypher
    assert "DURING_ENCOUNTER" not in cypher
    assert "LIMIT 500" in cypher
    assert response.json()["patient_id"] == "Patient/p-1"
    assert response.json()["events"][0]["value"] == 0


@pytest.mark.parametrize("patient_id", ["p-1", "Patient/p-1"])
def test_summary_graph_accepts_both_patient_id_forms(
    api: tuple[TestClient, RecordingSession], patient_id: str
) -> None:
    client, session = api
    session.results = [
        [
            {
                "patientId": "Patient/p-1",
                "patientName": "Ada Shah",
                "gender": "female",
                "birthDate": "2000-02-29",
                "bundles": [],
            }
        ]
    ]
    response = client.get(f"/api/v1/patients/{patient_id}/summary-graph")
    assert response.status_code == 200
    assert session.calls[0][1]["id"] == "Patient/p-1"
    cypher = str(session.calls[0][0])
    assert "p.name_0_given_0" in cypher
    assert "p.birth_date AS birthDate" in cypher
    assert response.json()["nodes"][0]["properties"]["display_name"] == "Ada Shah"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/api/v1/cohorts/query", {"conditions": ["44054006"]}),
        ("GET", "/api/v1/cohorts/conditions?q=diabetes", None),
        ("GET", "/api/v1/patients?q=Ada", None),
        ("GET", "/api/v1/patients/p-1", None),
        ("GET", "/api/v1/patients/p-1/summary-graph", None),
        ("GET", "/api/v1/patients/p-1/timeline", None),
        ("GET", "/api/v1/graph/neighbors/Patient/p-1", None),
        ("GET", "/api/v1/graph/explore/Patient/p-1", None),
        (
            "GET",
            "/api/v1/graph/explore/Patient/p-1/expand?relationship=SUBJECT&target_label=Encounter",
            None,
        ),
        ("GET", "/api/v1/dashboard/summary", None),
    ],
)
def test_graph_reads_attach_real_driver_timeout(
    api: tuple[TestClient, RecordingSession], method: str, path: str, payload: dict[str, Any] | None
) -> None:
    client, session = api
    response = client.request(method, path, json=payload)
    assert response.status_code in (200, 404)
    assert session.calls
    for query, _, kwargs in session.calls:
        assert isinstance(query, Query)
        assert query.timeout == 30
        assert "timeout" not in kwargs


def test_condition_autocomplete_reads_flattened_codes(
    api: tuple[TestClient, RecordingSession],
) -> None:
    client, session = api
    session.results = [[{"code": "44054006", "name": "Type 2 diabetes mellitus"}]]
    response = client.get("/api/v1/cohorts/conditions?q=diabetes")
    assert response.status_code == 200
    cypher = str(session.calls[0][0])
    assert "c.code_coding_0_code AS code" in cypher
    assert "c.code_coding_0_display" in cypher
    assert response.json() == [{"code": "44054006", "name": "Type 2 diabetes mellitus"}]


@pytest.mark.parametrize(
    "path",
    [
        "/patients?limit=0",
        "/cohorts/conditions?limit=0",
        "/graph/explore/Patient/p-1/expand?relationship=SUBJECT&target_label=Encounter&limit=-1",
    ],
)
def test_nonpositive_query_limits_do_not_reach_neo4j(
    api: tuple[TestClient, RecordingSession], path: str
) -> None:
    client, session = api
    response = client.get(f"/api/v1{path}")
    assert response.status_code == 422
    assert session.calls == []
