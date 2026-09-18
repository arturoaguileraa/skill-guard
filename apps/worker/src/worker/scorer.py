"""Score an artifact by reusing the skillguard engine (the same one apps/jev
serves live). One process, one warm Jev client, batched calls."""

from __future__ import annotations

import os

from skillguard.bank import load_bank
from skillguard.engine import Engine
from skillguard.extract import artifact_from_text
from skillguard.score import Thresholds, score
from skillguard.testing import FakeClient

from worker.db import database_url


class Scorer:
    def __init__(self, fake: bool | None = None):
        bank = load_bank()
        has_key = bool(os.environ.get("TYPESAFE_API_KEY"))
        if fake is None and not has_key and not database_url().startswith("sqlite"):
            # Never let heuristic scores land silently in a shared database.
            raise RuntimeError(
                "TYPESAFE_API_KEY is not set; refusing to score into a non-SQLite "
                "database with the heuristic client. Set the key or pass --fake."
            )
        use_fake = fake if fake is not None else not has_key
        self.engine = Engine(bank, client=FakeClient()) if use_fake else Engine(bank)
        self.is_fake = use_fake
        self.bank = bank
        self.th = Thresholds()
        self.weights_version = bank.version

    def score_text(self, content: str, identity: str | None = None) -> dict:
        art = artifact_from_text(content, identity)
        reading = self.engine.read(art)
        if reading.error:
            raise RuntimeError(reading.error)
        v = score(reading, self.bank, self.th)
        return {
            "risk": v.risk,
            "decision": v.decision.value,
            "mean_confidence": v.mean_confidence,
            "integrity_warning": v.integrity_warning,
            "families": [
                {"family": f, "risk": round(r, 4),
                 "label": self.bank.families.get(f, {}).get("label", f)}
                for f, r in sorted(v.family_risk.items(), key=lambda kv: kv[1], reverse=True)
                if r > 0.05
            ],
            "signals": [
                {"id": q, "value": round(val, 4)} for q, val in v.top_signals[:5]
            ],
            "model": self.engine.model,
            "input_tokens": reading.input_tokens,
            "cost_usd": reading.cost_usd,
            "weights_version": self.weights_version,
        }
