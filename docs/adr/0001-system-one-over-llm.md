# 0001 — Use a System One model (Jev), not an LLM, for triage

**Status:** Accepted

## Context

Malware triage of agent artifacts is a fan-out of thousands of small, typed judgements ("does this read credentials?", "is behaviour hidden?"), not text generation. LLM-based security scanners suffer three chronic problems: they hallucinate findings (invented CVEs/IOCs), their "seems malicious" is uncalibrated and can't be automated on a confidence budget, and they are themselves an injection target (the artifact they read can instruct them).

TypeSafe's **Jev** is a "System One" model: it takes structured state + typed questions and returns typed values with calibrated probabilities, in one batched call, at ~$0.042/MTok input with free output and sub-second latency.

## Decision

Use Jev as the scoring core. The verdict is composed in code from atomic, typed questions; the LLM-shaped work (writing an analyst report) is out of scope or deferred to the small minority of artifacts that escalate.

## Consequences

- **Positive:** Output is type-constrained → cannot hallucinate a finding. Probabilities are calibrated → usable on a ROC curve and in a confidence-gated escalation band. It doesn't follow instructions or generate text → the prompt-injection surface that defeats LLM scanners is largely absent (measured adversarial risk shift ≈ 0.00). Cheap and fast enough to gate a pre-install hook or CI.
- **Negative / limits:** Jev is bad at numbers, counting, dates, and literal/indirection reasoning — mitigated by doing all such work deterministically in `extract/` (see [ADR-0004](0004-scoring-and-weights.md)). It gives no natural-language rationale, so explainability comes from the per-question decomposition, not prose. It does not treat input as hostile by default — handled in scoring ([ADR-0004](0004-scoring-and-weights.md)).
- Vendor dependency on TypeSafe; mitigated by the boundary in [ADR-0002](0002-microservice-monorepo-boundary.md).
