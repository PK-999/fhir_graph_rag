"""Create local demo configuration without overwriting an existing .env."""

import re
import secrets
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / ".env"
    if target.exists():
        print("Existing .env preserved.")
        return
    content = (root / ".env.example").read_text()
    for name in ("POSTGRES_PASSWORD", "NEO4J_PASSWORD"):
        content = re.sub(
            rf"^{name}=.*$", f"{name}={secrets.token_urlsafe(24)}", content, flags=re.MULTILINE
        )
    with target.open("x") as stream:
        stream.write(content)
    target.chmod(0o600)
    print("Created .env with local database credentials.")


if __name__ == "__main__":
    main()
