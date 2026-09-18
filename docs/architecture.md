# Architecture

## Overview

skillguard is a monorepo of three request-time apps (`web`, `server`, `jev`) plus a batch `worker`, sharing one Postgres database. Each app has one job and a clean boundary to the next.

```
┌────────────┐   oRPC /rpc/*   ┌────────────┐   HTTP /analyze  ┌────────────┐   HTTPS   ┌─────────┐
│  apps/web  │ ───────────────▶│ apps/server│ ────/catalog────▶│  apps/jev  │ ─────────▶│ Jev API │
│  (browser) │                 │  (Hono)    │                  │  (FastAPI) │           │(TypeSafe)│
└────────────┘                 └────────────┘                  └────────────┘           └─────────┘
   React/Vite                    typed BFF                      scoring engine            System One
   TanStack Router               oRPC + Zod                     + question bank           model
                                                                + Jev API key
```

The TS side (`web`, `server`, `packages/api`) **never talks to Jev's API directly**. Only `apps/jev` holds the key and knows the question bank exists. Swapping the model vendor is a one-app change. See [ADR-0002](adr/0002-microservice-monorepo-boundary.md).

## Apps

### apps/jev — the scoring engine (Python)

The core. Pipeline:

1. **`extract/`** — deterministic fact extraction. An artifact (skill dir, pasted text, or MCP config) becomes a `state` object. Everything Jev is bad at — counting, path/host matching, comparisons — happens here in code (regex/parsing), never as a Jev question. See [ADR-0001](adr/0001-system-one-over-llm.md).
2. **`bank.py` + `questions/skill_bank.yaml`** — 18 typed questions (Noul / Choice / Score) grouped into 7 capability *families*, each with a tuned weight.
3. **`engine.py`** — one **batched** Jev call per artifact (all questions ride on one copy of the state — the economic invariant). Returns per-question values + calibrated confidence.
4. **`score.py`** — confidence-weighted noisy-OR within each family, then a weight-scaled noisy-OR across families → risk ∈ [0,1] → allow / escalate / block. A control question flags readings that adversarial text may have steered.

Exposed over HTTP by `service.py`:
- `POST /analyze` — score one artifact. Warm-connection keepalive + content-hash cache (see [ADR-0005](adr/0005-instant-provisional-and-latency.md)).
- `GET /catalog` — the static demo catalog (see [ADR-0006](adr/0006-static-synthetic-hub-catalog.md)); now only the no-database fallback.
- `GET /health` — reports whether it's running against real Jev or the heuristic fallback.

### apps/server — the BFF (TypeScript)

A thin Hono app that mounts the oRPC router at `/rpc`. `analyze` forwards to the Jev service (`JEV_SERVICE_URL`, default `http://localhost:8000`); `catalog` reads the results database directly when `DATABASE_URL` is set (falls back to jev's static catalog otherwise). No business logic beyond those two boundaries. `CORS_ORIGIN` is read from `process.env` — no `varlock` at runtime.

### packages/api — the contract (TypeScript)

The oRPC router (`analyze`, `catalog`, `artifact`) and Zod schemas. **`src/jev.ts` is the only place the TS side knows Jev exists**; **`src/catalog-db.ts` is the only place it reads the database** (keyset pagination, search, decision filter). End-to-end types flow from here to the web client.

### apps/web — the UI (TypeScript)

TanStack Router file-based routes:
- `/` **Tester** — live analyzer. Debounced (180ms) oRPC `analyze`; instant client-side heuristic preview replaced by the calibrated reading (the "real→real" invariant, [ADR-0005](adr/0005-instant-provisional-and-latency.md)). A **sensitivity panel** recomputes the verdict client-side from the returned family risks under user-adjusted weights + block threshold (same cross-family formula as `score.py`, `apps/web/src/lib/recompute.ts`) — no black box, no extra Jev call. On the `prettier-helper` example, a single **"Delete malware part"** button (in the presets row, outside the editor so it doesn't read as file text) removes the exfiltration paragraph (`findLure`/`removeLure` in `lib/skillguard.ts`); the verdict panel then shows a before → after strip built only from real readings (the react-query cache for the original text and the current fresh one), so it never shows a provisional number. "Put it back" restores the text.
- `/why` — value proposition.
- `/hub` — the analyzed-skills catalog via oRPC `catalog`: infinite scroll, debounced search, decision filter; keeps the previous list while a new query loads. Real artifacts show the verdict without a ground-truth claim, their repo/description, a commit-pinned GitHub link, and the stored `SKILL.md` text on demand (`artifact`, rendered as plain text).

Design language in [design-system.md](design-system.md).

## Request lifecycles

**Analyze (live tester):** keystroke → 180ms debounce → oRPC `analyze` → server → jev `/analyze` → (cache hit ~2ms, or Jev ~450ms warm) → typed result → dial updates. While in flight, the last real reading stays on screen.

**Catalog (hub):** page load / scroll / search → oRPC `catalog({ q, decision, cursor, limit })` → server → Neon (`results ⨝ artifacts`, keyset page) → rows + `next_cursor`. Without `DATABASE_URL`: server → jev `/catalog` → static `eval/catalog.json`.

**Ingest (worker):** `worker ingest-*` → `artifacts` + `jobs` → `worker run` claims jobs (`SKIP LOCKED`), scores with the same engine and Jev → `results` → visible in the hub on the next request.

## Deployment (production)

One Vercel project (`vercel.json`), three services deployed together; Neon Postgres; the worker is not deployed. See [ADR-0009](adr/0009-vercel-services-and-db-backed-hub.md).

```
Browser ──▶ jev-analysis.vercel.app
              ├─ /rpc/*  ──▶ server (Node fn) ──▶ Neon Postgres        (hub: reads results)
              │                  └─ binding ──▶ jev (Python fn, PRIVATE) ──▶ Jev API   (analyze)
              └─ /*      ──▶ web (static, CDN)

Maintainer's machine: worker ──▶ Neon (writes)  and  ──▶ Jev API (scores directly)
```

| Piece | Runs on | Notes |
|---|---|---|
| web | Vercel CDN | Static Vite build, SPA fallback, same-origin `/rpc` |
| server | Vercel Node function | Self-contained bundle; `entry.mjs` → `dist/index.mjs` |
| jev | Vercel Python function | No public route; reached only via the `JEV_SERVICE_URL` binding; holds `TYPESAFE_API_KEY` |
| database | Neon (Marketplace) | pooled `DATABASE_URL`; tables `artifacts`, `jobs`, `results` |
| worker | local for now | writes Neon with `apps/worker/.env`; a container host later |

Env vars on the project: `TYPESAFE_API_KEY` (sensitive), `CORS_ORIGIN`, the Neon set (`DATABASE_URL`, …). `JEV_SERVICE_URL` comes from the binding. A push to `main` builds production; other branches get protected previews.

## Ports (local dev)

| App | Port |
|---|---|
| web | 3001 |
| server | 3000 |
| jev | 8000 |

All started together by `bun run dev` (Turborepo).
