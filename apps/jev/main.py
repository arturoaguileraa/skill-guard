"""Vercel entrypoint: expose the FastAPI app from the src-layout package."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from skillguard.service import app  # noqa: E402,F401
