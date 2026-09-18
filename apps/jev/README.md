# skillguard

Calibrated triage of **agent-facing artifacts** — Claude Code skills and MCP
servers — using a System One model ([Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)).

An agent skill or MCP server is arbitrary text and code an AI agent _loads and
obeys_. That makes it an injection surface with almost no tooling around it.
skillguard reads one before you trust it and returns a **calibrated risk with a
routing decision** — not a chatbot opinion.

> This is the **engine package** of the skillguard monorepo (`apps/jev`). For the whole project — the web UI, the server, and how the three fit together — see the [root README](../../README.md) and [`docs/`](../../docs).

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
uv run python -m pytest -q

# real readings:
export TYPESAFE_API_KEY=sk-...
uv run skillguard --real scan ~/.claude/skills
```

## Results on real Jev (68-artifact corpus)

Evaluated against `jev-latest` on 68 labelled artifacts (34 malicious / 34
benign), ~$0.0001 and sub-second per artifact:

| metric | value |
| --- | --- |
| ROC-AUC | **1.000** |
| ECE (calibration error) | **0.205** |
| margin min(mal) − max(ben) | **+0.181** |
| adversarial injection Δ | **≈ 0.00** |
| benign false auto-blocks | **0 / 34** |
| malicious blocked | **34 / 34** |

The headline is the adversarial row: because Jev doesn't follow instructions or
generate text, injecting "audited, ignore warnings" into a malicious artifact
barely moves the risk — the injection surface that defeats LLM scanners isn't
there. Full method, dataset sources, and weight-tuning rationale in
[`eval/REPORT.md`](eval/REPORT.md) and [`../../docs/evaluation.md`](../../docs/evaluation.md).

## Tooling (all under `apps/jev`)

```bash
uv sync                                            # deps
uv run python -m pytest -q                          # engine tests
uv run python eval/harness.py --real run            # ROC-AUC + ECE
uv run python eval/harness.py --real adversarial    # injection robustness
uv run python eval/tune_weights.py                  # tune family weights (cached, 0 API calls to re-run)
uv run python eval/build_catalog.py                 # regenerate eval/catalog.json for the web hub

# CLI over local skills (no key needed with --fake):
uv run skillguard --fake scan ~/.claude/skills
uv run skillguard --real explain ~/.claude/skills/tdd
```

Family weights live in `src/skillguard/questions/skill_bank.yaml`; the block
threshold in `src/skillguard/score.py`. See
[ADR-0004](../../docs/adr/0004-scoring-and-weights.md) for the current values and why.
