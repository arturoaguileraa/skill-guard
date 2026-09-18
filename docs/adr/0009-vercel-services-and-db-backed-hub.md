# 0009 — Deploy on Vercel Services; the hub reads Neon directly

**Status:** Accepted

## Context

[ADR-0008](0008-mass-analysis-worker.md) built a worker that scores skills at scale into Postgres, and left two things open: where the apps run in production, and how the hub reads the results instead of the static `catalog.json` ([ADR-0006](0006-static-synthetic-hub-catalog.md)).

## Decision

**One Vercel project, three services** (`vercel.json`), shipped atomically:

- `web` (`apps/web`) — static Vite build on the CDN, SPA fallback.
- `server` (`apps/server`) — Hono + oRPC as a Node function, routed from `/rpc/*`.
- `jev` (`apps/jev`) — FastAPI as a Python function. **Private:** it has no public rewrite; only `server` reaches it through a service binding (`JEV_SERVICE_URL`). It is the only service holding `TYPESAFE_API_KEY`.

**Neon Postgres** (Vercel Marketplace) is the store. The `server` reads it directly for the hub, over `DATABASE_URL` with the HTTP driver — no provider SDK beyond a Postgres driver, so the URL stays swappable.

**The hub is paginated server-side.** `catalog` takes `{ q, decision, cursor, limit }` and returns the same shape plus optional `total`, `next_cursor`, `escalate`, `source`. Pagination is a **keyset cursor** over `(risk desc, artifact_hash desc)`; search is `ILIKE` backed by `pg_trgm` indexes created by `worker init-db`. With no `DATABASE_URL` it falls back to the static catalog (same input/output), so `bun run dev` needs no database.

**You can see what was scored.** Each artifact keeps its full text (`artifacts.content`) plus `repo`, `path`, and the frontmatter `name`/`description` (parsed deterministically at ingest; `worker backfill-meta` fills older rows). Catalog items carry those fields, the GitHub link is a **commit-pinned permalink** (so it can't drift from what we scored), and a new `artifact({ slug })` procedure returns the stored text (capped at 200k chars) on demand. The hub renders it as **plain text only** — it is adversary-controlled. `skills.sh` is not linked: it answers 200 for any path, so a link can't be verified.

**The worker stays out of Vercel** (persistent daemon). For now it runs on the maintainer's machine against the same Neon database; a container host is a later, mechanical step.

## Consequences

- **Positive:** the whole app ships together (skew protection, atomic rollback); the Jev key and spend are unreachable except through `server`; the hub reflects the worker live, and deep pages cost the same as the first.
- **A deliberate exception to [ADR-0002](0002-microservice-monorepo-boundary.md):** the TS side now reads the *results database* directly. That is a plain data read, not scoring — it still never talks to Jev's API, and `analyze` still goes `server → jev`.
- **Real artifacts have no ground-truth label.** `label`/`correct` only fit the shared shape; the UI keys off `synthetic` and shows the verdict, not a "matches its label" claim.
- **Negative / follow-up:** `/rpc/analyze` is public and unmetered (needs a rate limit); jev on serverless loses the warm-connection benefit of [ADR-0005](0005-instant-provisional-and-latency.md) between invocations; the worker daemon and a daily spend cap are still to do.

## Verdict names

The UI says **benign / suspicious / malicious**; the contract, the engine and the database keep `allow` / `escalate` / `block` (mapping in `VERDICT_LABEL`, `apps/web/src/lib/skillguard.ts`). Renaming only the presentation avoids a contract change and a data migration. Note "malicious" on a real third-party repo means the score crossed the block line, not that a person confirmed it — the hub says so.

## Gotchas learned

- The `server` bundle must be **self-contained** (`tsdown` `alwaysBundle`) and must not use `varlock` at runtime — it shells out to its own CLI, which a function does not ship. `entry.mjs` (in git) re-exports the built `dist/index.mjs`; the service `entrypoint` is validated before the build, so it can't point at `dist/` directly.
- `.vercelignore` must exclude `.env`/`.env.local` (CLI uploads otherwise bake `localhost` URLs into the bundle) but **not** `.env.schema` (varlock codegen needs it).
