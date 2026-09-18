"""apps/jev -- the Jev microservice.

The single job of this app: given raw artifact text, return a calibrated,
auditable risk reading. It is the only process that holds the TypeSafe API key
and the only one that knows the question bank exists. The TS server talks to it
over HTTP and never sees Jev directly -- that is the abstraction boundary.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from pathlib import Path
from collections import OrderedDict
from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from skillguard._env import load_dotenv
from skillguard.bank import load_bank
from skillguard.engine import Engine
from skillguard.extract import artifact_from_text
from skillguard.score import Thresholds, score
from skillguard.testing import FakeClient

load_dotenv()

# The connection to the Jev API is cold on first use (~890ms) and warm on reuse
# (~455ms) -- a 2x cliff. This loop keeps the pooled HTTPS connection hot so the
# live editor pays the warm price, not the cold one.
KEEPALIVE_SECONDS = 30


@contextlib.asynccontextmanager
async def _lifespan(app: FastAPI):
    async def warm() -> None:
        with contextlib.suppress(Exception):
            await asyncio.to_thread(_engine().read, artifact_from_text("warmup", "warmup"))

    await warm()  # establish the pool before the first real request

    async def keepalive() -> None:
        while True:
            await asyncio.sleep(KEEPALIVE_SECONDS)
            await warm()

    task = asyncio.create_task(keepalive())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="skillguard jev service", version="0.1.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # only the TS server calls this; it runs on localhost
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str = Field(default="", description="Raw SKILL.md content from the editor")
    identity: str | None = None


class Signal(BaseModel):
    id: str
    family: str
    value: float
    confidence: float
    weight: float


class FamilyRisk(BaseModel):
    family: str
    risk: float
    weight: float
    label: str


class AnalyzeResponse(BaseModel):
    identity: str
    risk: float
    decision: str
    mean_confidence: float
    integrity_warning: str | None
    families: list[FamilyRisk]
    signals: list[Signal]
    input_tokens: int
    cost_usd: float
    latency_ms: float
    model: str
    request_id: str | None
    error: str | None = None


@lru_cache(maxsize=1)
def _engine() -> Engine:
    bank = load_bank()
    if os.environ.get("TYPESAFE_API_KEY"):
        return Engine(bank)
    # No key -> heuristic fallback so the UI still lights up in dev.
    return Engine(bank, client=FakeClient())


# Content-hash cache: identical editor snapshots (revert, re-type, or repeated
# debounce frames) return instantly instead of paying another Jev round-trip.
_CACHE: OrderedDict[tuple[str, str | None], AnalyzeResponse] = OrderedDict()
_CACHE_MAX = 256


@app.get("/health")
def health() -> dict[str, object]:
    eng = _engine()
    return {
        "ok": True,
        "model": eng.model,
        "live": not isinstance(eng.client, FakeClient),
        "cache_size": len(_CACHE),
    }


def _compute(req: AnalyzeRequest) -> AnalyzeResponse:
    eng = _engine()
    bank = eng.bank
    art = artifact_from_text(req.text, req.identity)
    reading = eng.read(art)
    verdict = score(reading, bank, Thresholds())

    families = [
        FamilyRisk(family=fam, risk=r,
                   weight=bank.families.get(fam, {}).get("weight", 0.0),
                   label=bank.families.get(fam, {}).get("label", fam))
        for fam, r in sorted(verdict.family_risk.items(), key=lambda kv: kv[1], reverse=True)
    ]
    signals = [
        Signal(id=qid, family=bank.specs[qid].family, value=reading.values[qid],
               confidence=reading.confidence.get(qid, 0.0), weight=bank.specs[qid].weight)
        for qid in sorted(reading.values, key=lambda q: reading.values[q], reverse=True)
        if bank.specs[qid].family != "control" and bank.specs[qid].type != "choice"
    ]

    return AnalyzeResponse(
        identity=verdict.identity,
        risk=verdict.risk,
        decision=verdict.decision.value,
        mean_confidence=verdict.mean_confidence,
        integrity_warning=verdict.integrity_warning,
        families=families,
        signals=signals,
        input_tokens=reading.input_tokens,
        cost_usd=reading.cost_usd,
        latency_ms=reading.latency_ms,
        model=eng.model,
        request_id=reading.request_id,
        error=reading.error,
    )


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    key = (req.text, req.identity)
    cached = _CACHE.get(key)
    if cached is not None and cached.error is None:
        _CACHE.move_to_end(key)
        # Report a cache hit as ~0ms so the client can distinguish it.
        return cached.model_copy(update={"latency_ms": 0.0})

    result = _compute(req)
    if result.error is None:
        _CACHE[key] = result
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return result


# --- analyzed-skills catalog (the web "hub") --------------------------------
# Static reference data: our labeled+scored corpus, built offline by
# eval/build_catalog.py from cached Jev readings. Served as-is.
_CATALOG_PATH = Path(__file__).resolve().parents[2] / "eval" / "catalog.json"


@app.get("/catalog")
def catalog() -> dict[str, object]:
    try:
        return json.loads(_CATALOG_PATH.read_text())
    except OSError:
        return {"count": 0, "items": [], "malicious": 0, "benign": 0,
                "thresholds": {"block": 0.8, "review": 0.35}, "generated_at": "", "model": ""}
