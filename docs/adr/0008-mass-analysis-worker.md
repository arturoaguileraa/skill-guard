# 0008 — Mass-analysis worker + database-backed catalog

**Status:** Accepted (worker built; DB provisioning + hub wiring pending)

## Context

The hub started as a static `catalog.json` of 68 synthetic fixtures ([ADR-0006](0006-static-synthetic-hub-catalog.md)). To become a real "is this skill safe" catalog it must analyze **thousands** of real skills/MCP servers continuously and persist the results — a long-running, stateful, throughput-bound job, unlike the request/response apps.

## Decision

A new `apps/worker` (Python) that reuses the `skillguard` engine (installed as an editable path dep on `apps/jev`) to **ingest → queue → score → store** at scale:

- **Storage is provider-neutral** via `DATABASE_URL`: a SQLite file locally, managed **Neon Postgres** in production (Vercel Marketplace, auto-injected env). No provider SDK is hardcoded — SQLAlchemy over the connection string.
- **The queue is a Postgres `jobs` table** claimed with `FOR UPDATE SKIP LOCKED`, so many worker replicas run safely with no extra queue service. SQLite degrades to a single-worker transaction for dev.
- **Idempotent** by content hash; re-ingesting is a no-op.
- **Ingestion sources:** local paths (backfill) and GitHub code search (scale, rate-limited).
- The worker `export-catalog` writes the same `catalog.json` shape the hub reads today, so results flow to the UI with no UI change yet.

## Deployment

- `apps/web` + `apps/server` → **Vercel** (their sweet spot).
- `apps/worker` → a **container host** (Railway / Fly.io / Render), NOT Vercel functions — it's a persistent daemon, the opposite of a 300s serverless function. Scale replicas horizontally (SKIP LOCKED).
- `apps/jev` → container host too (keeps the warm Jev connection, [ADR-0005](0005-instant-provisional-and-latency.md)), or Vercel Python if single-cloud is preferred.
- Database → **Neon Postgres**; the `jobs` table doubles as the queue.

## Consequences

- **Positive:** One engine, reused across live (`apps/jev`) and batch (`apps/worker`). Horizontally scalable, cheap (~$8 of Jev to score 100k artifacts). No extra queue infra. Storage swaps by changing a URL.
- **Negative / follow-up:** The hub still reads static `catalog.json` — the clean next step is a paginated API on `apps/server` reading Neon directly. Ingestion throughput is capped by GitHub code-search rate limits; more sources needed for millions. A per-day spend guard is advisable. DB provisioning needs the Vercel CLI + the user's account (not yet done).
