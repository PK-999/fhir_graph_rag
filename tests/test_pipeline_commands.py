"""Pipeline commands must use one dataset and the configured local services."""

from pathlib import Path

import pytest
from pipelines import build_graph, load_fhir, reconcile, run_all


def test_full_pipeline_cli_forwards_generation_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[tuple[int, int, Path]] = []

    async def run(patients: int, seed: int, output: Path, config: object) -> str:
        seen.append((patients, seed, output))
        return "test-run"

    monkeypatch.setattr(run_all, "run_pipeline", run)
    monkeypatch.setattr(
        "sys.argv", ["run_all", "--patients", "2", "--seed", "7", "--output", str(tmp_path)]
    )
    run_all.main()
    assert seen == [(2, 7, tmp_path)]


@pytest.mark.parametrize("module", [load_fhir, reconcile])
def test_fhir_commands_use_env_file_url(
    module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FHIRGRAPH_ENV_FILE", raising=False)
    monkeypatch.delenv("HAPI_FHIR_URL", raising=False)
    (tmp_path / ".env").write_text("HAPI_FHIR_URL=http://localhost:59080/fhir\n")
    summary = tmp_path / "data_quality_summary.json"
    summary.write_text('{"resource_counts": {"Patient": 1}}')
    seen: list[str] = []

    async def load(directory: Path, url: str, concurrency: int) -> dict[str, int]:
        seen.append(url)
        return {"total": 1, "success": 1, "failure": 0}

    async def count(path: Path, url: str) -> bool:
        seen.append(url)
        return True

    if module is load_fhir:
        monkeypatch.setattr(load_fhir, "load_bundles", load)
        monkeypatch.setattr("sys.argv", ["load_fhir", "--input", str(tmp_path)])
        load_fhir.main()
    else:
        monkeypatch.setattr(reconcile, "reconcile_counts", count)
        monkeypatch.setattr("sys.argv", ["reconcile", "--input", str(summary)])
        with pytest.raises(SystemExit) as exc:
            reconcile.main()
        assert exc.value.code == 0

    assert seen == ["http://localhost:59080/fhir"]


def test_empty_bundle_directory_is_not_a_successful_load(tmp_path: Path) -> None:
    import asyncio

    with pytest.raises(ValueError, match="No bundle files"):
        asyncio.run(load_fhir.load_bundles(tmp_path, "http://unused.invalid/fhir"))


def test_loader_rejects_zero_concurrency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["load_fhir", "--input", str(tmp_path), "--concurrency", "0"])
    with pytest.raises(SystemExit) as exc:
        load_fhir.main()
    assert exc.value.code == 2


def test_graph_command_uses_env_file_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FHIRGRAPH_ENV_FILE", raising=False)
    for variable in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"):
        monkeypatch.delenv(variable, raising=False)
    (tmp_path / ".env").write_text(
        "NEO4J_URI=bolt://localhost:59687\nNEO4J_USER=test-reader\nNEO4J_PASSWORD=test-password\n"
    )
    seen: list[tuple[str, str, str]] = []

    async def build(directory: Path, uri: str, user: str, password: str) -> dict[str, object]:
        seen.append((uri, user, password))
        return {"success": True, "nodes_loaded": 1, "edges_loaded": 0, "derived_edges": 0}

    monkeypatch.setattr(build_graph, "build_graph", build)
    monkeypatch.setattr("sys.argv", ["build_graph", "--input", str(tmp_path)])

    build_graph.main()

    assert seen == [("bolt://localhost:59687", "test-reader", "test-password")]
