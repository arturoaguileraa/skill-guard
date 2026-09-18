"""The Jev call: one batched request per artifact.

Batching is the whole economic argument. The artifact body dominates the
request, so N separate questions would re-send it N times. One call sends it
once and evaluates every question in parallel against it.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

from typesafe_sdk import TypeSafeClient, TypeSafeError

from skillguard.artifact import Artifact
from skillguard.bank import Bank

PRICE_PER_INPUT_MTOK = 0.042  # USD, per typesafe.ai pricing; output is free


def _maybe_request_id(response) -> str | None:
    try:
        return response.request_id
    except TypeSafeError:
        return None


@dataclass
class Reading:
    """Raw model output for one artifact, before any judgment is composed."""

    artifact: Artifact
    values: dict[str, float]
    confidence: dict[str, float]
    detail: dict[str, Any]
    input_tokens: int
    latency_ms: float
    request_id: str | None = None
    error: str | None = None

    @property
    def cost_usd(self) -> float:
        return self.input_tokens / 1_000_000 * PRICE_PER_INPUT_MTOK


class Engine:
    def __init__(self, bank: Bank, client: TypeSafeClient | None = None, model: str | None = None):
        self.bank = bank
        self.model = model or os.environ.get("TYPESAFE_MODEL", "jev-latest")
        self.client = client or TypeSafeClient()

    def read(self, artifact: Artifact) -> Reading:
        started = time.perf_counter()
        try:
            response = self.client.system_one(
                artifact.to_state(), self.bank.questions, model=self.model
            )
        except TypeSafeError as exc:
            return Reading(artifact, {}, {}, {}, 0, (time.perf_counter() - started) * 1000,
                           error=f"{type(exc).__name__}: {exc}")

        latency_ms = (time.perf_counter() - started) * 1000
        values: dict[str, float] = {}
        confidence: dict[str, float] = {}
        detail: dict[str, Any] = {}

        for qid, spec in self.bank.specs.items():
            answer = response.answers.get(qid)
            if answer is None:
                continue
            if spec.type == "noul":
                # A noul IS the calibrated probability; there is no separate
                # confidence field, so we use distance from 0.5 as decisiveness.
                values[qid] = float(answer.noul)
                confidence[qid] = abs(float(answer.noul) - 0.5) * 2
                detail[qid] = {"noul": float(answer.noul)}
            elif spec.type == "score":
                # Normalize onto [0,1] so families mix on one scale.
                span = max(spec.n_levels - 1, 1)
                values[qid] = float(answer.score) / span
                confidence[qid] = float(answer.confidence)
                detail[qid] = {
                    "score": float(answer.score),
                    "legend": answer.legend,
                    "probabilities": answer.probabilities,
                }
            else:  # choice -- carried for evidence, not folded into the risk sum
                values[qid] = 0.0
                confidence[qid] = float(answer.confidence)
                detail[qid] = {
                    "choice": answer.choice,
                    "probabilities": answer.probabilities,
                }

        return Reading(
            artifact=artifact,
            values=values,
            confidence=confidence,
            detail=detail,
            input_tokens=response.usage.input_tokens,
            latency_ms=latency_ms,
            request_id=_maybe_request_id(response),
        )
