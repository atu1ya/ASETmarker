"""Utility script to scaffold a local .env file."""
from __future__ import annotations

import secrets
from pathlib import Path

ENV_TEMPLATE = """# Environment configuration for ASET Marking System
SECRET_KEY={secret}
STAFF_PASSWORD=everest2024
DEBUG=true
"""


def main() -> None:
    env_path = Path(".env")
    if env_path.exists():
        print(".env already exists. No changes made.")
        return

    secret = secrets.token_hex(32)
    env_path.write_text(ENV_TEMPLATE.format(secret=secret), encoding="utf-8")
    print("Created .env with generated SECRET_KEY. Please review the file before deployment.")


if __name__ == "__main__":
    main()
