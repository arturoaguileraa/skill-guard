# CLAUDE.md

Guidance for agents working in this repo. Keep it current when architecture or commands change.

## What this is

**skillguard** — calibrated malware-risk triage for **agent-facing artifacts** (Claude Code skills, MCP servers). It scores an artifact with a **System One model (TypeSafe Jev)** — typed, calibrated probabilities, not free-form text — and routes it allow / escalate / block. See `docs/architecture.md` and `docs/adr/` for the why.

## Monorepo layout (Bun + Turborepo)

| Path | Stack | Role |
|---|---|---|
| `apps/web` | React 19 · Vite · TanStack Router · TS | UI: live playground (`/`), value prop (`/why`), analyzed-skills hub (`/hub`) |
| `apps/server` | Hono · oRPC · TS | Typed BFF the web calls; forwards to the Jev service |
| `apps/jev` | FastAPI · `typesafe-sdk` · Python | **The only process holding the Jev API key and the question bank.** The scoring engine. |
| `apps/worker` | Python · SQLAlchemy · reuses `skillguard` | Mass-analysis: ingest skills at scale, score with Jev, store results in a DB. Batch/daemon, not part of `bun run dev`. See [ADR-0008](docs/adr/0008-mass-analysis-worker.md). |
| `packages/api` | oRPC router + Zod | `analyze` + `catalog` + `artifact` procedures; `src/jev.ts` is the sole TS↔Jev boundary |
| `packages/ui` | shadcn (base-lyra) on base-ui, Tailwind v4 | Shared components |

Data flow: **analyze:** web → `/rpc/*` (server) → `POST /analyze` (jev) → Jev API. **catalog (hub):** web → `/rpc/*` (server) → Neon Postgres (`DATABASE_URL`), else jev `GET /catalog` (static fallback). The TS side never talks to Jev's API directly — that boundary is deliberate (ADR-0002); reading the results DB is the one deliberate exception (ADR-0009). Production is one Vercel project with three services (ADR-0009, `docs/architecture.md`).

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
- **Verdict names:** the UI says benign / suspicious / malicious; the contract, engine and DB keep allow / escalate / block (`VERDICT_LABEL`). Don't rename the internal values. Thresholds: block 0.80, review 0.55, plus "malicious" needs deception evidence ≥ 0.40 (ADR-0004 amendments 1 and 3); `decide()` in `score.py` is the single rule — the web `recompute.ts` mirrors it.
- **Filling the catalog** (worker, from `apps/worker`): `worker ingest-topics` (crawl top repos per GitHub topic; needs `GITHUB_TOKEN`) → `worker run --forever --concurrency 16 --max-usd-day 5` (daily spend cap shared through the DB) → `worker rethreshold` after any threshold change (0 API calls); after any question/bank change, `worker requeue` (re-scores; stores every reading in `results.readings`). Changing question wording invalidates the eval cache: `cd apps/jev && uv run python eval/tune_weights.py --refresh` (~100 calls), then `eval/build_catalog.py`. Skills only — no MCP sources. Real cost ≈ $0.00027/skill.
- **Stored artifact text is untrusted:** the hub shows it as plain text only (`<pre>`), never markdown/HTML. Don't render it richly.
- **The hub reads Neon in production** (paginated by keyset cursor; real artifacts have no ground-truth label). Without `DATABASE_URL` it falls back to the static demo catalog, generated offline from cached readings — regenerate after corpus/weight changes: `cd apps/jev && uv run python eval/build_catalog.py`.

## Gotchas

- **Deploying:** `vercel deploy --prod` (or push to `main`). Verify with `curl` to `/rpc/*` **and** grep the built JS for `localhost`. The server bundle must stay self-contained and free of runtime `varlock`; `.vercelignore` must not exclude `.env.schema` (ADR-0009).
- **Mobile (the tester):** on touch or <640px, `compact` mode replaces the in-text "select it, hit ⌫" tag (it covers text and there is no ⌫ key) with a full-width "Tap to delete it" button that doesn't focus the textarea (no keyboard), and a fixed `VerdictBar` shows the live verdict — with the before → after on delete — whenever the verdict panel is off-screen. Editor/search inputs are 16px on phones (iOS zooms into smaller fields) and tap targets are ≥44px. Test with real mobile emulation (CDP `Emulation.setDeviceMetricsOverride`, touch events), **not** `chrome --window-size`: headless Chrome clamps the window to ~500px and fakes overflow.
- **Link previews:** `apps/web/index.html` carries Open Graph + Twitter tags; the image is a real screenshot of the landing page, `apps/web/public/og.png` (1200×628, ~130 KB — WhatsApp drops big ones). Regenerate it when the first screen changes: `bash apps/web/scripts/og-image.sh` (macOS: Chrome headless + sips; captures production). Tags are static (crawlers don't run JS), so every route shares them; the URLs are absolute and point at `https://jev-analysis.vercel.app`.
- **Worker DB target:** only the `worker` CLI loads `.env`; ad-hoc `python -c` does not and silently falls back to local SQLite. The worker refuses heuristic scoring into Postgres without `TYPESAFE_API_KEY`.

- base-ui `TooltipTrigger` uses `render={<el/>}`, **not** `asChild`.
- Fonts load from Google Fonts in `apps/web/index.html`; `--font-sans` / `--font-mono` are overridden in `apps/web/src/index.css` (after the shared globals import).
- `apps/web/src/env.ts` and `routeTree.gen.ts` are generated — don't hand-edit.
- Tuning weights: use `apps/jev/eval/tune_weights.py` (caches Jev readings in `eval/.readings_cache.json`; re-runs cost 0 API calls). Family weights live in `apps/jev/src/skillguard/questions/skill_bank.yaml`.

## Where to read more

- `docs/architecture.md` — the three-app design and boundaries
- `docs/design-system.md` — the UI language
- `docs/evaluation.md` — corpus, metrics, how to re-run/tune (full report in `apps/jev/eval/REPORT.md`)
- `docs/adr/` — the decisions and their trade-offs
