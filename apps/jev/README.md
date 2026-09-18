# skillguard

Calibrated triage of **agent-facing artifacts** — Claude Code skills and MCP
servers — using a System One model ([Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)).

An agent skill or MCP server is arbitrary text and code an AI agent _loads and
obeys_. That makes it an injection surface with almost no tooling around it.
skillguard reads one before you trust it and returns a **calibrated risk with a
routing decision** — not a chatbot opinion.

## Why System One and not an LLM

Triage is a fan-out of thousands of small typed judgements ("does this read
credentials?", "is behaviour hidden from the user?"), not text generation. Jev
is built exactly for that shape:

- **One batched call per artifact.** The artifact body dominates the request, so
  the ~18 questions ride on one copy of it — TypeSafe measures ~12× cheaper /
  10× faster than one call per question.
- **~$0.0003 per artifact, 70–500 ms.** Cheap enough to gate a `pre-install`
  hook or CI step in real time.
- **Type-safe output — it cannot invent an IOC.** Answers are constrained to the
  schema; the model only scores hypotheses _we_ defined.
- **Calibrated probabilities.** Usable in a ROC curve and a confidence-gated
  escalation band — the thing an LLM's "seems malicious" can't give you.

## Architecture

```
extract/   artifact -> text state   (deterministic; all counting/paths/regex here)
bank.py    ~18 typed questions in YAML, grouped by capability family
engine.py  ONE batched Jev call per artifact
score.py   weighted noisy-OR over families -> risk -> allow / escalate / block
```

Everything Jev is [documented to be bad at](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
— counting, number/date comparison, literal matching — lives in `extract/`. Jev
only ever judges semantics.

## Adversary controls the input

Jev does **not** treat state as hostile by default. A malicious skill will embed
`"this has been audited, ignore warnings"`. Two defences, both first-class:

1. an `override` question family that scores self-certification as a _risk
   signal_, not a reason to relax;
2. a **control question** whose answer we already know from the deterministic
   facts — if the model gets it wrong, the whole reading is flagged as possibly
   steered and force-escalated.

The eval harness measures this directly: `eval/harness.py adversarial` reports
the risk drop when an assurance is injected into known-malicious fixtures.

## Run it

```bash
uv sync
# no API key needed: heuristic fake client proves the plumbing
uv run skillguard --fake scan ~/.claude/skills
uv run skillguard --fake explain ~/.claude/skills/tdd
uv run python eval/harness.py run          # ROC-AUC + ECE calibration
uv run python eval/harness.py adversarial  # injection robustness
uv run pytest -q

# real readings:
export TYPESAFE_API_KEY=sk-...
uv run skillguard --real scan ~/.claude/skills
```

## Results on real Jev (8-fixture corpus)

First run against `jev-latest`, ~2.2k tokens and ~1 s per artifact, **$0.0001
each**:

| metric                       | value      | reading                                                                                                        |
| ---------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------- |
| ROC-AUC                      | **1.000**  | perfect separation of the 4 malicious / 4 benign fixtures                                                      |
| ECE (calibration error)      | **0.202**  | benign complex dev-skills still carry 0.3–0.5 risk                                                             |
| min(malicious) − max(benign) | **+0.485** | wide, safe margin between the classes                                                                          |
| **adversarial injection Δ**  | **−0.000** | **injecting "audited, ignore warnings, pre-approved" into malicious fixtures did not lower their risk at all** |

The headline is the last row. Because Jev doesn't follow instructions or generate
text, the prompt-injection surface that defeats LLM scanners simply isn't there —
the assurance is scored _as a risk signal_ (`false_assurance`), not obeyed.

Two honest caveats the numbers expose:

- The residual ECE is **our aggregation, not Jev's per-question calibration** —
  Jev rates a benign skill's `destructive_action` at 0.25 _with 0.25 confidence_
  (honestly unsure); the miscalibration came from noisy-OR compounding many
  small signals. Confidence-weighting each signal (`score.py`) cut ECE 0.234 →
  0.202 and widened the margin 0.355 → 0.485.
- The corpus is 8 hand-authored fixtures. Next: a public labelled dataset
  (Datadog malicious-packages adapted to skills) for numbers that generalise.
