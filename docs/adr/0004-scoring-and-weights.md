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

## Amendment (2026-09-18): review threshold 0.35 → 0.55

The block threshold (0.80) is unchanged. The **review** threshold was tuned on the 68 synthetic fixtures, whose benign median is already ~0.38. Scoring the first 190 real public skills gave the same picture (median 0.38; p25 0.32, p75 0.47), so at 0.35 about **63%** of clearly benign real skills landed in review — the split between "review" and "allow" was noise around the median, not signal (spot checks of skills just above 0.35 were ordinary code-review, docs and design skills).

Every malicious fixture scores ≥ 0.95, so a higher review threshold costs them nothing. At **0.55**, review holds ~12% of real skills. `decide()` in `score.py` is the single rule; `worker rethreshold` re-decides stored results from stored risk with no Jev call.

**Caveat:** the corpus has no *subtle* malicious example between 0.35 and 0.55, so recall in that band is unmeasured; a subtle attack scoring there now reads as benign. Adding hard positives is the way to close this.

## Amendment (2026-09-18, 2): false positives on real skills — per-question strength, question wording v3

**Finding.** On ~5,000 real public skills, 297 (5.7%) were `block`. Reading them showed four kinds of false positive: (1) a repo's own **test fixtures** (e.g. a malware scanner's samples) presented as a publisher's skills; (2) ordinary **vendor installers/APIs** — `unpinned_remote_source` alone drove ~75% of the blocks (Jev reads any non-registry vendor domain as "unpinned"); (3) **workflow language**: `hides_from_user` counted "silently" / "no prompt" (e.g. "silently take Path B"); (4) **memory/notes skills** that record the conversation in the user's own vault, flagged by `harvests_conversation`.

**Changes (bank v2 → v3).**
- `strength` per question (new, default 1.0): `unpinned_remote_source` is damped to **0.35** inside `remote_code`; `fetch_and_execute` keeps full strength. Simulated then confirmed exactly: 0/34 malicious fixtures lost.
- `hides_from_user` and `harvests_conversation` reworded to require *concealing a specific action / capturing conversation for a destination the user did not ask for*, and to exclude prompt-skipping and local notes.
- Ingestion skips `tests/`, `fixtures/`, `__tests__/`, `testdata/` paths (`is_test_path`).

**Result.** Fixtures: 34/34 malicious still `block` (lowest 0.913, was 0.946), AUC 1.000, 68/68 correct. Real skills: `block` 297 → 44 of 6,587 (0.7%); `github`, `dotnet`, `microsoft` official skills: 0 blocks (were 8, 0, 3+). The remaining non-test blocks are mostly offensive-security education and skills that really fetch and run code.

**Not done, deliberately.** `tune_weights.py` suggests different family weights; they are *not* applied — 68 synthetic fixtures with all malicious ≥ 0.9 cannot justify moving them. **Caveats:** recall on subtle real attacks is unmeasured (the corpus has none), and Jev's reading of "vendor domain" is still the weak point: the long-term fix is deterministic host classification in `extract/`.

**Infrastructure.** `results.readings` now stores every question's raw value and confidence, so weights and thresholds can be re-tuned over real data offline (no Jev call). `worker requeue` re-scores after a bank change; `worker prune-tests` removes test-path artifacts.
