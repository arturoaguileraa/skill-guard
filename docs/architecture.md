# Architecture

## Overview

skillguard is a three-app monorepo. Each app has one job and a clean boundary to the next.

```
┌────────────┐   oRPC /rpc/*   ┌────────────┐   HTTP /analyze  ┌────────────┐   HTTPS   ┌─────────┐
│  apps/web  │ ───────────────▶│ apps/server│ ────/catalog────▶│  apps/jev  │ ─────────▶│ Jev API │
│  (browser) │                 │  (Hono)    │                  │  (FastAPI) │           │(TypeSafe)│
└────────────┘                 └────────────┘                  └────────────┘           └─────────┘
   React/Vite                    typed BFF                      scoring engine            System One
   TanStack Router               oRPC + Zod                     + question bank           model
                                                                + Jev API key
```

The TS side (`web`, `server`, `packages/api`) **never talks to Jev directly**. Only `apps/jev` holds the key and knows the question bank exists. Swapping the model vendor is a one-app change. See [ADR-0002](adr/0002-microservice-monorepo-boundary.md).

## Apps

### apps/jev — the scoring engine (Python)

The core. Pipeline:

1. **`extract/`** — deterministic fact extraction. An artifact (skill dir, pasted text, or MCP config) becomes a `state` object. Everything Jev is bad at — counting, path/host matching, comparisons — happens here in code (regex/parsing), never as a Jev question. See [ADR-0001](adr/0001-system-one-over-llm.md).
2. **`bank.py` + `questions/skill_bank.yaml`** — 18 typed questions (Noul / Choice / Score) grouped into 7 capability *families*, each with a tuned weight.
3. **`engine.py`** — one **batched** Jev call per artifact (all questions ride on one copy of the state — the economic invariant). Returns per-question values + calibrated confidence.
4. **`score.py`** — confidence-weighted noisy-OR within each family, then a weight-scaled noisy-OR across families → risk ∈ [0,1] → allow / escalate / block. A control question flags readings that adversarial text may have steered.

Exposed over HTTP by `service.py`:
- `POST /analyze` — score one artifact. Warm-connection keepalive + content-hash cache (see [ADR-0005](adr/0005-instant-provisional-and-latency.md)).
- `GET /catalog` — the static analyzed-skills catalog for the hub (see [ADR-0006](adr/0006-static-synthetic-hub-catalog.md)).
- `GET /health` — reports whether it's running against real Jev or the heuristic fallback.

### apps/server — the BFF (TypeScript)

A thin Hono app that mounts the oRPC router at `/rpc` and forwards to the Jev service. Holds no business logic beyond the boundary. `JEV_SERVICE_URL` (default `http://localhost:8000`).

### packages/api — the contract (TypeScript)

The oRPC router (`analyze`, `catalog`) and Zod schemas. **`src/jev.ts` is the only place the TS side knows Jev exists** — it fetches the Jev service and validates the response. End-to-end types flow from here to the web client.

### apps/web — the UI (TypeScript)

TanStack Router file-based routes:
- `/` **Tester** — live analyzer. Debounced (180ms) oRPC `analyze`; instant client-side heuristic preview replaced by the calibrated reading (the "real→real" invariant, [ADR-0005](adr/0005-instant-provisional-and-latency.md)).
- `/why` — value proposition.
- `/hub` — the analyzed-skills catalog via oRPC `catalog`.

Design language in [design-system.md](design-system.md).

## Request lifecycles

**Analyze (live tester):** keystroke → 180ms debounce → oRPC `analyze` → server → jev `/analyze` → (cache hit ~2ms, or Jev ~450ms warm) → typed result → dial updates. While in flight, the last real reading stays on screen.

**Catalog (hub):** page load → oRPC `catalog` → server → jev `/catalog` → static `eval/catalog.json` (generated offline from cached readings) → searchable table.

## Ports

| App | Port |
|---|---|
| web | 3001 |
| server | 3000 |
| jev | 8000 |

All started together by `bun run dev` (Turborepo).
