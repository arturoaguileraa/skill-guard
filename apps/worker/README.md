# @jev-analysis/worker

Mass-analysis worker: ingest agent skills / MCP servers **at scale**, score each
with Jev by reusing the `skillguard` engine, and **store the results** in a
database. This is what turns the demo hub into a real, growing catalog.

> Part of the skillguard monorepo. See the [root docs](../../docs). The engine it
> reuses lives in [`apps/jev`](../jev) (installed here as an editable path dep).

## Pipeline

```
ingest ──▶ [ artifacts + jobs table ] ──▶ worker loop ──▶ [ results table ] ──▶ hub
 GitHub /                 (queue)          claim→score→save                export-catalog
 local dir                                  (skillguard + Jev)
```

- **Idempotent** — artifacts are keyed by content hash; re-ingesting is a no-op.
- **Queue** — a Postgres `jobs` table claimed with `FOR UPDATE SKIP LOCKED`, so
  you can run **many worker replicas** safely. On SQLite (single-worker dev) it
  degrades to a plain transaction.
- **Provider-neutral storage** — everything speaks `DATABASE_URL`: a SQLite file
  locally, managed Postgres (Neon) in production. No code change, just the URL.
- **Cost-aware** — one warm Jev client, batched calls; without a key it falls
  back to the heuristic client so the pipeline runs offline.

## Usage

```bash
uv sync
cp .env.example .env            # optional: DATABASE_URL, TYPESAFE_API_KEY, GITHUB_TOKEN

uv run worker init-db
uv run worker ingest-local ~/.claude/skills ../jev/eval/fixtures   # backfill
uv run worker ingest-github --query "filename:SKILL.md" --max 200  # scale (needs GITHUB_TOKEN)
uv run worker ingest-topics --max-repos 150   # crawl top repos per GitHub topic (SKILL.md)
uv run worker ingest-repos anthropics/skills  # or specific repos
uv run worker run --batch 48 --concurrency 16 --max-usd-day 5   # drain the queue once (capped)
uv run worker rethreshold             # re-decide stored results under current thresholds (0 API calls)
uv run worker backfill-meta           # fill repo/path/name/description on old rows
uv run worker run --forever           # daemon: keep scoring as jobs arrive
uv run worker stats
uv run worker export-catalog ../jev/eval/catalog.json   # feed the web hub
```

## Modules

| file | role |
|---|---|
| `db.py` | SQLAlchemy schema (`artifacts`, `jobs`, `results`) + engine from `DATABASE_URL` |
| `store.py` | enqueue / claim (SKIP LOCKED) / complete / fail / stats — idempotent by hash |
| `ingest.py` | sources: local paths and GitHub code search (rate-limited, paged) |
| `scorer.py` | reuses the `skillguard` engine — same scoring as the live service |
| `run.py` | the claim→score→save loop (one-shot or `--forever`) |
| `sources.py` | bulk sources: GitHub repo-tree crawl per topic/repo (scales past code search's 1,000 cap) |
| `meta.py` | deterministic frontmatter + GitHub-URL parsing (`name`, `description`, `repo`, `path`) |
| `export_catalog.py` | dump results to the hub's `catalog.json` shape |

## Next steps

- Point the web **hub** at the DB directly (paginated API) instead of the static
  `catalog.json`, so it reflects the worker live.
- Add more ingestion sources (MCP registries, npm packages carrying skills).
- Schedule the daemon and add a small budget guard (max spend / day).
