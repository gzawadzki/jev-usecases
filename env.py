"""Load TYPESAFE_API_KEY from the environment or the nearest .env."""

from __future__ import annotations

import os
from pathlib import Path


def load_api_key() -> str:
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return key.strip()
    here = Path(__file__).resolve().parent
    for folder in (Path.cwd(), here, *here.parents):
        env_path = folder / ".env"
        if not env_path.is_file():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("TYPESAFE_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"')
                if value:
                    return value
    raise SystemExit("Set TYPESAFE_API_KEY or put it in a .env file at the repo root.")
