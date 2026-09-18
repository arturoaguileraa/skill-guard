# skillguard

**Calibrated malware-risk triage for agent-facing artifacts** — Claude Code skills and MCP servers.

An agent skill or MCP server is arbitrary text and code an AI agent *loads and obeys*. That makes it an injection surface with almost no tooling around it. skillguard reads one before you trust it and returns a **calibrated risk with a routing decision** — powered by a System One model ([TypeSafe Jev](https://typesafe.ai/blog/introducing-system-one-models-and-jev)), not a chatbot.

Three sections — a live tester, a value-prop page, and a hub of everything we've analyzed. See [`docs/architecture.md`](docs/architecture.md).

## Why a System One model, not an LLM

Triage is a fan-out of thousands of small typed judgements ("does this read credentials?", "is behaviour hidden from the user?"), not text generation. Jev is built for exactly that:

- **Calibrated probabilities** you can put on a ROC curve and gate on — an LLM's "seems malicious" can't be automated on a confidence budget.
- **Type-safe output** — it only scores hypotheses we defined, so it physically can't hallucinate a CVE/IOC/API.
- **Injection-resistant** — it doesn't follow instructions or write text, so pasting "this has been audited, ignore warnings" into a malicious skill barely moved the risk (Δ≈0.00, measured).
- **~$0.0001 and sub-second** per artifact — cheap and fast enough to gate a pre-install hook or CI.

Full argument and honest limits in [`docs/adr/0001-system-one-over-llm.md`](docs/adr/0001-system-one-over-llm.md).

## The app

Three sections (see it at `http://localhost:3001`):

- **Tester** (`/`) — paste a skill/MCP; it's scored the moment you stop typing, decomposed into the signals that drove it.
- **Why** (`/why`) — the value proposition and a System One vs. LLM comparison.
- **Hub** (`/hub`) — every artifact we've analyzed, with its verdict and signals, searchable. (A demo corpus of synthetic-but-grounded fixtures — not an authoritative registry of real skills.)

## Architecture (monorepo, Bun + Turborepo)

```
apps/web      React + Vite + TanStack Router   → :3001   the three UIs
apps/server   Hono + oRPC                       → :3000   typed BFF
apps/jev      FastAPI + typesafe-sdk (Python)   → :8000   scoring engine; holds the Jev key
packages/api  oRPC router + Zod                           the sole TS↔Jev boundary
```

Flow: **analyze:** web → server (`/rpc/*`) → jev (`/analyze`) → Jev API · **hub:** web → server → Neon Postgres (filled by `apps/worker`). Details in [`docs/architecture.md`](docs/architecture.md).

## Run

```bash
cd apps/jev && uv sync && cd ../..     # one-time: Python deps
# put your TypeSafe key in apps/jev/.env  (TYPESAFE_API_KEY=...)  — gitignored
bun run dev                            # web :3001 · server :3000 · jev :8000
```

Without a key, `apps/jev` uses a heuristic fallback so the UI still works (`/health` → `"live": false`).

## The engine (`apps/jev`)

`extract/` (deterministic facts — all counting/paths/regex, since Jev is bad at numbers) → `bank.py` (18 typed questions in YAML, grouped by capability family) → `engine.py` (one batched Jev call) → `score.py` (confidence-weighted noisy-OR → allow/escalate/block).

Evaluation on a 68-artifact labeled corpus (real Jev): **ROC-AUC 1.00 · ECE 0.205 · 0/34 benign false-blocks · adversarial Δ≈0.00**. Method, sources and tuning in [`docs/evaluation.md`](docs/evaluation.md) and [`apps/jev/eval/REPORT.md`](apps/jev/eval/REPORT.md).

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — guide for agents working in the repo
- [`docs/architecture.md`](docs/architecture.md) · [`docs/design-system.md`](docs/design-system.md) · [`docs/evaluation.md`](docs/evaluation.md)
- [`docs/adr/`](docs/adr/) — architecture decision records
