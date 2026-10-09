"""Verify the Milestone 0 API and web HTTP surfaces."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    name: str
    url: str
    expected_status: str | None = None


def wait_for_check(check: Check, timeout_seconds: float) -> None:
    """Poll one HTTP surface until it returns its expected healthy response."""
    deadline = time.monotonic() + timeout_seconds
    last_error = "no response"

    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(check.url, timeout=min(timeout_seconds, 2.0)) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"HTTP {response.status}")
                if check.expected_status is not None:
                    payload = json.load(response)
                    if payload.get("status") != check.expected_status:
                        raise RuntimeError(
                            f"expected status={check.expected_status!r}, got {payload.get('status')!r}"
                        )
            print(f"{check.name}: ok")
            return
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
            last_error = str(exc)
            time.sleep(0.1)

    raise TimeoutError(f"{check.name} failed: {last_error}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8010/api/v1")
    parser.add_argument("--web-url", default="http://127.0.0.1:4010")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checks = (
        Check("api-liveness", f"{args.api_url.rstrip('/')}/health/live", "ok"),
        Check("api-readiness", f"{args.api_url.rstrip('/')}/health/ready", "ok"),
        Check("web", args.web_url.rstrip("/")),
    )
    try:
        for check in checks:
            wait_for_check(check, args.timeout)
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
