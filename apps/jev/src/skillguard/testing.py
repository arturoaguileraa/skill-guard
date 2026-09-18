"""In-memory Jev stand-in.

Lets the whole pipeline -- extraction, batching shape, scoring, routing, eval
metrics -- run and be tested with zero network and no API key. It is NOT a
model: it applies transparent heuristics over the SAME state Jev would see, so
a green pipeline here means the plumbing is correct, not that detection works.
Swap in TypeSafeClient for real readings.
"""

from __future__ import annotations

from typing import Any

from typesafe_sdk import ChoiceAnswer, NoulAnswer, ScoreAnswer, SystemOneResponse, Usage


class _Answers(dict):
    def get(self, key, default=None):  # noqa: D401 - dict-compatible accessor
        return super().get(key, default)


class FakeClient:
    """Heuristic responder that mirrors the SystemOneResponse contract."""

    def __init__(self, rules=None):
        self.rules = rules or _default_rules
        self.calls = 0

    def system_one(self, state: dict[str, Any], questions, *, model=None, **_) -> SystemOneResponse:
        self.calls += 1
        blob = _flatten(state).lower()
        facts = state.get("computed_facts", {}) if isinstance(state, dict) else {}
        answers = _Answers()
        for qid, q in questions.items():
            qtype = q.model_dump().get("type")
            if qtype == "noul":
                answers[qid] = NoulAnswer(type="noul", noul=self.rules(qid, blob, facts, "noul"))
            elif qtype == "score":
                levels = len(q.model_dump()["criteria"])
                s = self.rules(qid, blob, facts, "score") * (levels - 1)
                probs = _peak(levels, s)
                answers[qid] = ScoreAnswer(type="score", score=s, confidence=0.8,
                                           legend={i: "" for i in range(levels)}, probabilities=probs)
            else:
                opts = list(q.model_dump()["criteria"])
                probs = {o: 1.0 / len(opts) for o in opts}
                answers[qid] = ChoiceAnswer(type="choice", choice=opts[0], confidence=0.5, probabilities=probs)
        tokens = max(len(_flatten(state)) // 4, 1)
        return SystemOneResponse(model=model or "fake", usage=Usage(input_tokens=tokens, output_tokens=0),
                                 answers=answers)

    # context-manager parity with the real client
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _flatten(obj: Any) -> str:
    if isinstance(obj, dict):
        return " ".join(f"{k} {_flatten(v)}" for k, v in obj.items())
    if isinstance(obj, list):
        return " ".join(_flatten(x) for x in obj)
    return str(obj)


def _peak(levels: int, score: float) -> dict[str, float]:
    lo = int(score)
    frac = score - lo
    probs = {i: 0.0 for i in range(levels)}
    probs[lo] = 1 - frac
    if lo + 1 < levels:
        probs[lo + 1] = frac
    total = sum(probs.values()) or 1.0
    return {k: v / total for k, v in probs.items()}


def _default_rules(qid: str, blob: str, facts: dict, qtype: str) -> float:
    """Cheap keyword heuristics keyed by question id. Enough to exercise routing."""
    f = facts
    strong = {
        "reads_credentials": bool(f.get("sensitive_path_mentions")),
        "sends_data_offhost": bool(f.get("hosts_outside_common_allowlist")) and bool(f.get("network_or_encoding_verbs")),
        "harvests_conversation": "conversation" in blob and ("post" in blob or "upload" in blob),
        "hides_from_user": bool(f.get("instruction_override_phrases")) and "do not tell" in blob,
        "conditional_trigger": "if the user says" in blob or "when you see" in blob,
        "persistence": "settings.json" in blob or "crontab" in blob or ".zshrc" in blob or ".bashrc" in blob,
        "overrides_agent_rules": "ignore previous" in blob or "you are now" in blob,
        "false_assurance": "has been audited" in blob or "pre-approved" in blob or "this is safe" in blob,
        "disables_confirmation": "without asking" in blob or "skip confirmation" in blob or "auto-approve" in blob,
        "fetch_and_execute": ("curl" in blob or "wget" in blob) and ("| sh" in blob or "| bash" in blob or "eval" in blob),
        "unpinned_remote_source": bool(f.get("hosts_outside_common_allowlist")),
        "tool_escalation": "allowed-tools" in blob and "bypass" in blob,
        "encoded_payload": (f.get("long_base64_blobs", 0) or 0) > 0 or (f.get("hex_escape_runs", 0) or 0) > 0,
        "misleading_naming": False,
    }
    if qid in strong:
        return 0.9 if strong[qid] else 0.05
    if qid == "control_states_purpose":
        return 0.95  # control: assume description present unless we know otherwise
    if qtype == "score":
        if qid == "capability_beyond_purpose":
            return 0.66 if f.get("network_or_encoding_verbs") else 0.1
        if qid == "destructive_action":
            return 0.9 if ("rm -rf" in blob or "force" in blob or "revoke" in blob) else 0.15
    return 0.1
