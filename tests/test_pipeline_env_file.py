"""A selected Compose environment also selects the pipeline destination."""

import json
import os
import subprocess
import sys
from pathlib import Path


def test_pipeline_uses_selected_environment_file(tmp_path: Path) -> None:
    config = tmp_path / "isolated.env"
    config.write_text("POSTGRES_PORT=55499\nHAPI_FHIR_URL=http://localhost:58999/fhir\n")
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"POSTGRES_PORT", "HAPI_FHIR_URL"}
    }
    env["FHIRGRAPH_ENV_FILE"] = str(config)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; from pipelines.config import PipelineSettings; s=PipelineSettings(); print(json.dumps([s.postgres_port,s.hapi_fhir_url]))",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout) == [55499, "http://localhost:58999/fhir"]
