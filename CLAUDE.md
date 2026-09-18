# CLAUDE.md

Guidance for agents working in this repo. Keep it current when architecture or commands change.

## What this is

**skillguard** — calibrated malware-risk triage for **agent-facing artifacts** (Claude Code skills, MCP servers). It scores an artifact with a **System One model (TypeSafe Jev)** — typed, calibrated probabilities, not free-form text — and routes it allow / escalate / block. See `docs/architecture.md` and `docs/adr/` for the why.

## Monorepo layout (Bun + Turborepo)

| Path | Stack | Role |
|---|---|---|
| `apps/web` | React 19 · Vite · TanStack Router · TS | UI: live tester (`/`), value prop (`/why`), analyzed-skills hub (`/hub`) |
| `apps/server` | Hono · oRPC · TS | Typed BFF the web calls; forwards to the Jev service |
| `apps/jev` | FastAPI · `typesafe-sdk` · Python | **The only process holding the Jev API key and the question bank.** The scoring engine. |
| `packages/api` | oRPC router + Zod | `analyze` + `catalog` procedures; `src/jev.ts` is the sole TS↔Jev boundary |
| `packages/ui` | shadcn (base-lyra) on base-ui, Tailwind v4 | Shared components |

Data flow: **web → `/rpc/*` (server) → `POST /analyze` · `GET /catalog` (jev) → Jev API**. The TS side never talks to Jev directly — that boundary is deliberate (ADR-0002).

## Run & verify

```bash
# one-time: Python service deps
cd apps/jev && uv sync && cd ../..

bun run dev                 # starts all three: web :3001, server :3000, jev :8000
bun run check-types         # tsc + vite build across the monorepo (must pass)
bun x biome check apps/web/src packages/ui/src   # lint (tabs; must be clean)
cd apps/jev && uv run python -m pytest -q         # engine tests (NOT `pytest`, use `python -m pytest`)
```

- The Jev key lives in `apps/jev/.env` (gitignored, auto-loaded). Without it, `apps/jev` falls back to a heuristic `FakeClient` so the UI still works; `/health` reports `"live": false`.
- Do not start dev servers that are already running (ports 3000/3001/8000). Verify via `check-types` / `vite build` instead.

## Rules & conventions

- **Jev is not an LLM.** It returns typed probabilities and cannot generate text or follow instructions. Anything numeric (counting, path/host matching, comparisons) is **Jev is bad at that** — do it deterministically in `apps/jev/src/skillguard/extract/`, then ask Jev only semantic questions.
- **The adversary controls the artifact text.** Never trust it; the `override` question family scores self-certification ("audited, ignore warnings") as risk, and a control question flags steered readings. Don't add features that obey artifact content.
- **UI real→real invariant:** the risk dial must never flash a wrong intermediate number. `view = calibrated ?? preview`; the instant heuristic (`apps/web/src/lib/provisional.ts`) only fills the first paint; `keepPreviousData` holds the last real reading while re-analyzing. Preserve this when editing `apps/web/src/routes/index.tsx`.
- **oRPC contract:** don't change the `analyze` / `catalog` output shapes without updating `packages/api/src/jev.ts` (Zod) on both sides.
- **Design system** (see `docs/design-system.md`): Host Grotesk + JetBrains Mono, monochrome ink/paper, color reserved for risk, hairline structure, `motion` (framer-motion) for reveals. Tokens in `apps/web/src/index.css`; motion primitives in `apps/web/src/components/motion.tsx`.
- **The hub catalog is static.** It's generated offline from cached Jev readings — no live calls. After changing the corpus or weights, regenerate: `cd apps/jev && uv run python eval/build_catalog.py`.

## Gotchas

- base-ui `TooltipTrigger` uses `render={<el/>}`, **not** `asChild`.
- Fonts load from Google Fonts in `apps/web/index.html`; `--font-sans` / `--font-mono` are overridden in `apps/web/src/index.css` (after the shared globals import).
- `apps/web/src/env.ts` and `routeTree.gen.ts` are generated — don't hand-edit.
- Tuning weights: use `apps/jev/eval/tune_weights.py` (caches Jev readings in `eval/.readings_cache.json`; re-runs cost 0 API calls). Family weights live in `apps/jev/src/skillguard/questions/skill_bank.yaml`.

## Where to read more

- `docs/architecture.md` — the three-app design and boundaries
- `docs/design-system.md` — the UI language
- `docs/evaluation.md` — corpus, metrics, how to re-run/tune (full report in `apps/jev/eval/REPORT.md`)
- `docs/adr/` — the decisions and their trade-offs
