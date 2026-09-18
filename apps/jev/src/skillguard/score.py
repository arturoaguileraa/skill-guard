"""Compose atomic readings into a verdict.

Deliberately arithmetic, not learned: every number here is traceable to a named
question, so a finding can always be explained as "this question said 0.91".
Thresholds are the only tunable, and they are set from the eval harness, not
from taste.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import prod

from skillguard.bank import Bank
from skillguard.engine import Reading


class Decision(str, Enum):
    ALLOW = "allow"
    ESCALATE = "escalate"
    BLOCK = "block"


@dataclass(frozen=True)
class Thresholds:
    # Tuned on the 68-artifact eval corpus (see eval/REPORT.md). With the tuned
    # family weights the risk distributions separate cleanly: the highest-scoring
    # benign hard-negative sits at ~0.77 and the lowest-scoring malicious at
    # ~0.95, so 0.80 falls in the empty gap -- it auto-blocks every malicious
    # fixture while routing credential-adjacent-but-legitimate tools (e.g. a
    # migration skill that reads .env) to human review instead of a false block.
    block: float = 0.80
    # 0.35 was tuned on the 68 synthetic fixtures, but their benign median is
    # already ~0.38, and so is that of 190 real public skills -- so 0.35 sent
    # ~63% of clearly benign real skills to review. Every malicious fixture
    # scores >= 0.95 (auto-block), so raising review to 0.55 costs them nothing
    # and leaves ~12% of real skills in review. Caveat: the corpus has no subtle
    # malicious example between 0.35 and 0.55, so recall there is unmeasured.
    review: float = 0.55
    min_confidence: float = 0.45
    # "malicious" (block) needs at least this much evidence of DECEPTION (see
    # QuestionSpec.deception). Risky-but-transparent capability -- installing with
    # curl|sh, reading an API key from .env -- stays "suspicious". On 82 real
    # blocks only 3 had any deception evidence; 0.4 sits between the weakest real
    # malicious fixtures (0.62) and the benign fixtures (<= 0.33).
    min_deception: float = 0.40


@dataclass
class Verdict:
    identity: str
    kind: str
    risk: float
    decision: Decision
    family_risk: dict[str, float]
    top_signals: list[tuple[str, float]]
    mean_confidence: float
    integrity_warning: str | None = None
    notes: list[str] = field(default_factory=list)
    deception: float = 0.0


def noisy_or(values: list[float]) -> float:
    """P(at least one) under an independence assumption.

    Independence is wrong -- these signals correlate -- but it is wrong in the
    conservative direction for a triage filter, and it keeps the combinator
    monotone: no single question can lower a risk another one raised.
    """
    return 1.0 - prod(1.0 - min(max(v, 0.0), 1.0) for v in values) if values else 0.0


def decide(risk: float, mean_conf: float, integrity: str | None,
           th: Thresholds, deception: float | None = None) -> tuple["Decision", str | None]:
    """Risk -> decision. Pure, so stored results can be re-decided offline when
    thresholds change (see `worker rethreshold`) without any Jev call."""
    if integrity:
        return Decision.ESCALATE, "escalated on integrity warning"
    if risk >= th.block:
        if mean_conf >= th.min_confidence:
            if deception is not None and deception < th.min_deception:
                return Decision.ESCALATE, (
                    f"risk {risk:.2f} over block threshold but no evidence of deception "
                    f"({deception:.2f}) -- risky capability only")
            return Decision.BLOCK, None
        return Decision.ESCALATE, (
            f"risk {risk:.2f} over block threshold but confidence {mean_conf:.2f} is low")
    if risk >= th.review:
        return Decision.ESCALATE, None
    return Decision.ALLOW, None


def score(reading: Reading, bank: Bank, thresholds: Thresholds | None = None) -> Verdict:
    th = thresholds or Thresholds()
    notes: list[str] = []

    if reading.error:
        return Verdict(
            reading.artifact.identity, reading.artifact.kind, 0.0, Decision.ESCALATE,
            {}, [], 0.0, notes=[f"engine error: {reading.error}"],
        )

    # Confidence-weight each signal before it accumulates. Jev's calibration is
    # per-question, so a value it is only 0.25-confident about should not
    # compound like a certain one -- otherwise many small, uncertain signals
    # noisy-OR their way to a false positive on a legitimately complex skill.
    by_family: dict[str, list[float]] = {}
    for qid, spec in bank.specs.items():
        if spec.family == "control" or spec.type == "choice":
            continue
        if qid in reading.values:
            weighted = (reading.values[qid] * reading.confidence.get(qid, 1.0)
                        * spec.strength)
            by_family.setdefault(spec.family, []).append(weighted)

    family_risk = {fam: noisy_or(vals) for fam, vals in by_family.items()}

    # Weighted noisy-OR across families: a maxed-out low-weight family can never
    # by itself reach the block threshold, but several mid ones can.
    risk = 1.0 - prod(
        1.0 - bank.families.get(fam, {}).get("weight", 0.0) * r
        for fam, r in family_risk.items()
    ) if family_risk else 0.0

    scored = bank.scored_ids()
    confidences = [reading.confidence[q] for q in scored if q in reading.confidence]
    mean_conf = sum(confidences) / len(confidences) if confidences else 0.0

    top = sorted(
        ((q, v) for q, v in reading.values.items()
         if bank.specs[q].family not in ("control",) and bank.specs[q].type != "choice"),
        key=lambda kv: kv[1], reverse=True,
    )[:5]

    # Integrity check: a control question whose answer we already know from the
    # deterministic facts. Getting it wrong means the response as a whole is
    # suspect -- most likely the artifact text steered the model.
    integrity = None
    ctrl = reading.values.get("control_states_purpose")
    if ctrl is not None:
        truth = bool(str(reading.artifact.declared.get("description") or "").strip())
        if (ctrl > 0.5) != truth:
            integrity = (
                f"control question disagrees with ground truth "
                f"(said {ctrl:.2f}, actual description present={truth}); "
                f"treat this reading as possibly steered"
            )

    deception = max(
        (reading.values[q] * reading.confidence.get(q, 1.0)
         for q, spec in bank.specs.items() if spec.deception and q in reading.values),
        default=0.0,
    )
    decision, note = decide(risk, mean_conf, integrity, th, deception)
    if note:
        notes.append(note)

    return Verdict(
        identity=reading.artifact.identity,
        kind=reading.artifact.kind,
        risk=risk,
        decision=decision,
        family_risk=family_risk,
        top_signals=top,
        mean_confidence=mean_conf,
        deception=deception,
        integrity_warning=integrity,
        notes=notes,
    )
