"""Executable contracts for the Milestone 0 development bootstrap."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPOSE_COMMAND = [
    "docker",
    "compose",
    "--env-file",
    ".env.example",
    "-f",
    "infra/docker-compose.yml",
    "-f",
    "infra/docker-compose.dev.yml",
]


def render_compose_config() -> dict[str, Any]:
    """Render the same merged Compose model used by local development."""
    result = subprocess.run(
        [*COMPOSE_COMMAND, "config", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    rendered: dict[str, Any] = json.loads(result.stdout)
    return rendered


def test_compose_configuration_is_renderable() -> None:
    """Malformed or incomplete Compose configuration must fail the bootstrap gate."""
    result = subprocess.run(
        [*COMPOSE_COMMAND, "config", "--quiet"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_declared_build_files_exist() -> None:
    """Every image declared by Compose must have a real Dockerfile."""
    compose = render_compose_config()

    for service_name in ("api", "web"):
        dockerfile = compose["services"][service_name]["build"]["dockerfile"]
        assert (ROOT / dockerfile).is_file(), (
            f"{service_name} declares missing build file {dockerfile}"
        )


def test_host_ports_use_the_fhirgraph_namespace_defaults() -> None:
    """The stack must avoid common ports already used by unrelated projects."""
    compose = render_compose_config()

    assert compose["services"]["api"]["ports"][0]["published"] == "8010"
    assert compose["services"]["web"]["ports"][0]["published"] == "4010"


def test_api_and_web_have_container_healthchecks() -> None:
    """Compose readiness ordering requires health checks on application services."""
    compose = render_compose_config()

    assert "healthcheck" in compose["services"]["api"]
    assert "healthcheck" in compose["services"]["web"]


def test_hapi_readiness_uses_api_http_probe_instead_of_a_jvm_process_check() -> None:
    """The distroless JVM executable does not prove the FHIR server is ready."""
    compose = render_compose_config()
    assert "healthcheck" not in compose["services"]["hapi-fhir"]
    assert compose["services"]["api"]["depends_on"]["hapi-fhir"]["condition"] == "service_started"
    assert "health/ready" in str(compose["services"]["api"]["healthcheck"]["test"])
    assert (
        "currentSchema=hapi"
        in compose["services"]["hapi-fhir"]["environment"]["spring.datasource.url"]
    )


def test_make_exposes_milestone_zero_commands() -> None:
    """The documented developer commands must be syntactically executable."""
    for target in ("dev", "check", "smoke", "down"):
        result = subprocess.run(
            ["make", "--dry-run", target],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"make {target}: {result.stderr}"


def test_server_fetched_pages_are_explicitly_dynamic() -> None:
    """Production builds should not attempt API-backed pages during prerendering."""
    for relative_path in (
        "apps/web/src/app/page.tsx",
        "apps/web/src/app/data-quality/page.tsx",
        "apps/web/src/app/lineage/page.tsx",
    ):
        source = (ROOT / relative_path).read_text()
        assert 'export const dynamic = "force-dynamic";' in source
