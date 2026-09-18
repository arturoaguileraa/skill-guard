"""Zero-dependency .env loader. Walks up from CWD to find a .env and populates
os.environ for any key not already set. Called once at CLI/harness startup so a
gitignored .env supplies TYPESAFE_API_KEY without a manual export."""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(start: Path | None = None) -> None:
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        env = directory / ".env"
        if not env.is_file():
            continue
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        return
