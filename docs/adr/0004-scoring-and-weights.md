# 0004 — Confidence-weighted noisy-OR with tuned family weights

**Status:** Accepted

## Context

Jev answers ~18 typed questions per artifact, grouped into 7 capability *families* (exfiltration, covert, override, remote_code, scope, obfuscation, destructive). We need to combine them into one risk with an allow/escalate/block decision that is **auditable** (a verdict must decompose into named questions) and **calibrated** (benign hard-negatives that legitimately touch sensitive capabilities must not auto-block).

An early unweighted noisy-OR over all families compounded many small, uncertain signals into false positives on legitimately complex benign skills (e.g. a deploy skill scoring high on `destructive`).

## Decision

- Combine **confidence-weighted** per-question values (`value × confidence`) with noisy-OR within a family, then a weight-scaled noisy-OR across families. Confidence-weighting stops signals Jev is unsure about from compounding.
- **Tune family weights** and the block threshold against the labeled corpus, using a cached, bounded/regularised coordinate search (`eval/tune_weights.py`).
- Keep numeric/deterministic work (counting, path/host matching, entropy) out of Jev entirely — it lives in `extract/` (per [ADR-0001](0001-system-one-over-llm.md)).
- Treat the artifact as hostile: an `override` family scores self-certification ("audited, ignore warnings") as risk, and a control question (whose answer we know from the facts) flags readings that adversarial text may have steered → force-escalate.

## Consequences

- **Positive:** Confidence-weighting cut ECE (0.236 → 0.205) and widened the separation margin. Tuned weights took benign false auto-blocks from 4/34 to **0/34** while keeping 34/34 malicious blocked. Verdicts remain fully auditable (per-family, per-signal breakdown drives the UI and the hub).
- **Current values:** exfiltration 0.90, covert 0.85, remote_code 0.82, override 0.75, scope 0.40, obfuscation 0.30, destructive 0.25; block 0.80, review 0.35. Rationale: the high-severity families stay high enough that one saturated family still blocks alone; the families benign tools legitimately trip (destructive, scope) were lowered. The unconstrained optimum (which collapsed exfiltration to 0.20) was rejected as a corpus overfit.
- **Negative / follow-up:** Weights are tuned on 68 synthetic-but-grounded fixtures — a small, imperfect proxy for the wild. A cleaner long-term fix than lowering the exfiltration weight is to split "reads a secret" vs "sends a secret" inside that family. Residual ECE ≈ 0.20 is partly floored by hard negatives correctly sitting in the review band against a hard 0/1 label.
