"""Repository cleanup must preserve data, checkpoints and installed dependencies."""

import subprocess
from pathlib import Path


def assert_cleanup_preserves_workload(makefile: str, workspace: Path) -> None:
    (workspace / "Makefile").write_text(makefile)
    for directory in ("libs", "apps/api", "pipelines", "scripts", "tests"):
        (workspace / directory).mkdir(parents=True, exist_ok=True)
    protected = {
        "artifacts/bundles/patient.json": '{"id":"patient"}',
        "artifacts/ndjson/Patient.ndjson": '{"id":"patient"}\n',
        "artifacts/dataset_manifest.json": '{"dataset_hash":"known"}',
        "artifacts/data_quality_summary.json": '{"status":"pass"}',
        "artifacts/.checkpoints/load_fhir.json": '{"completed":{"bundle":"hash"}}',
        ".venv/lib/__pycache__/dependency.pyc": "installed dependency",
    }
    for relative, content in protected.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    cache = workspace / "libs/__pycache__/source.pyc"
    cache.parent.mkdir(parents=True)
    cache.write_text("source cache")
    result = subprocess.run(
        ["make", "clean"], cwd=workspace, text=True, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr
    for relative, content in protected.items():
        assert (workspace / relative).is_file(), f"Cleanup deleted {relative}"
        assert (workspace / relative).read_text() == content
    assert not cache.exists()


def test_make_clean_preserves_workload_and_installed_dependencies(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    assert_cleanup_preserves_workload((root / "Makefile").read_text(), tmp_path)
