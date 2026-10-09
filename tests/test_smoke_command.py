"""Behavior tests for the full-stack HTTP smoke command."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _HealthyHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/api/v1/health/live":
            body = {"status": "ok"}
            status = 200
        elif self.path == "/api/v1/health/ready":
            body = {"status": "ok", "dependencies": {}}
            status = 200
        else:
            body = {"status": "web-ok"}
            status = 200

        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


def test_smoke_command_checks_api_and_web_surfaces() -> None:
    """A healthy API and web server must make the smoke command succeed."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _HealthyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    try:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/smoke.py",
                "--api-url",
                f"http://127.0.0.1:{port}/api/v1",
                "--web-url",
                f"http://127.0.0.1:{port}",
                "--timeout",
                "1",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        server.shutdown()
        thread.join(timeout=2)

    assert result.returncode == 0, result.stderr
    assert "api-liveness: ok" in result.stdout
    assert "api-readiness: ok" in result.stdout
    assert "web: ok" in result.stdout
