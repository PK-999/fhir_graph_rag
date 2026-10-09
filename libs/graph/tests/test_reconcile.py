"""Streaming preflight remains compatible with exact graph reconciliation."""

import json
from pathlib import Path
from typing import Any

import pytest
from pipelines.config import PipelineSettings
from pipelines.reconcile import reconcile_graph


class Records:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        for row in self.rows:
            yield row


class Driver:
    def __init__(self, extra: bool) -> None:
        self.extra = extra

    def session(self):  # type: ignore[no-untyped-def]
        return self

    async def __aenter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def close(self) -> None:
        pass

    async def run(self, query: str) -> Records:
        if "type(r)" in query:
            return Records([{"source": "Observation/o", "kind": "SUBJECT", "target": "Patient/p"}])
        return Records(
            [{"id": "Patient/p"}, {"id": "Observation/o"}]
            + ([{"id": "Patient/leftover"}] if self.extra else [])
        )


@pytest.mark.parametrize("extra,expected", [(False, True), (True, False)])
async def test_reconciliation_consumes_streamed_input_and_detects_leftovers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: bool, expected: bool
) -> None:
    resources = [
        {"resourceType": "Patient", "id": "p"},
        {
            "resourceType": "Observation",
            "id": "o",
            "status": "final",
            "code": {"text": "Lab"},
            "subject": {"reference": "Patient/p"},
        },
    ]
    (tmp_path / "resources.ndjson").write_text(
        "\n".join(json.dumps(resource) for resource in resources) + "\n"
    )
    monkeypatch.setattr(
        "pipelines.reconcile.AsyncGraphDatabase.driver", lambda *args, **kwargs: Driver(extra)
    )
    assert (
        await reconcile_graph(tmp_path, PipelineSettings(_env_file=None, neo4j_password="test"))
        is expected
    )
