"""worker — ingest artifacts at scale, score them with Jev, store the results.

    uv run worker init-db
    uv run worker ingest-local ~/.claude/skills ../jev/eval/fixtures
    uv run worker ingest-github --query "filename:SKILL.md" --max 200
    uv run worker run --batch 16            # drain the queue
    uv run worker run --forever             # daemon mode
    uv run worker stats
    uv run worker export-catalog ../jev/eval/catalog.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from skillguard._env import load_dotenv

from worker.db import get_engine, init_db
from worker.export_catalog import export_catalog
from worker.ingest import ingest_github, ingest_paths
from worker.run import run
from worker.sources import (
    DEFAULT_TOPICS,
    ingest_repos,
    ingest_topics,
)
from worker.store import backfill_meta, prune_tests, requeue, rethreshold, stats


def main(argv=None) -> int:
    load_dotenv()
    # Dev convenience: the Jev key lives in apps/jev/.env. Never overrides
    # values already set (in prod the host injects env vars directly).
    load_dotenv(Path(__file__).resolve().parents[3] / "jev")
    p = argparse.ArgumentParser(prog="worker", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="create tables")

    pl = sub.add_parser("ingest-local", help="enqueue SKILL.md under paths")
    pl.add_argument("paths", nargs="+")

    pg = sub.add_parser("ingest-github", help="discover skills via GitHub code search")
    pg.add_argument("--query", default="filename:SKILL.md")
    pg.add_argument("--max", type=int, default=100)

    pt = sub.add_parser("ingest-topics", help="crawl top GitHub repos per topic for SKILL.md")
    pt.add_argument("--topic", action="append", help="repeatable; default: a curated set")
    pt.add_argument("--max-repos", type=int, default=200, help="per topic (search caps at 1000)")
    pt.add_argument("--max-skills", type=int, default=200, help="per repo")
    pt.add_argument("--sort", choices=["stars", "updated"], default="stars")

    prp = sub.add_parser("ingest-repos", help="crawl specific owner/repo for SKILL.md")
    prp.add_argument("repos", nargs="+")
    prp.add_argument("--max-skills", type=int, default=200)

    pr = sub.add_parser("run", help="score pending jobs")
    pr.add_argument("--batch", type=int, default=16)
    pr.add_argument("--concurrency", type=int, default=8)
    pr.add_argument("--max-usd-day", type=float, default=None,
                    help="daily Jev spend cap (default $5 or WORKER_MAX_USD_PER_DAY; 0 = off)")
    pr.add_argument("--quiet", action="store_true", help="progress summaries instead of per-skill lines")
    pr.add_argument("--forever", action="store_true")
    pr.add_argument("--fake", action="store_true", help="force the heuristic client")

    sub.add_parser("stats", help="queue + result counts")
    sub.add_parser("rethreshold", help="re-decide stored results under the current thresholds (0 API calls)")
    pq = sub.add_parser("requeue", help="re-score already-scored artifacts (after a bank change)")
    pq.add_argument("--decision", action="append", choices=["allow", "escalate", "block"],
                    help="repeatable; default: escalate + block")
    pp = sub.add_parser("prune-tests", help="find (and with --yes delete) artifacts under test/fixture paths")
    pp.add_argument("--yes", action="store_true", help="actually delete; default is a dry run")
    sub.add_parser("backfill-meta", help="fill repo/path/name/description on old rows")

    pe = sub.add_parser("export-catalog", help="dump results to a hub catalog.json")
    pe.add_argument("out")

    args = p.parse_args(argv)
    engine = get_engine()

    if args.cmd == "init-db":
        init_db(engine)
        print("tables created")
    elif args.cmd == "ingest-local":
        init_db(engine)
        n = ingest_paths(engine, [Path(x).expanduser() for x in args.paths])
        print(f"enqueued {n} new artifacts")
    elif args.cmd == "ingest-github":
        init_db(engine)
        n = ingest_github(engine, query=args.query, max_results=args.max)
        print(f"enqueued {n} new artifacts from GitHub")
    elif args.cmd == "ingest-topics":
        init_db(engine)
        out = ingest_topics(engine, topics=tuple(args.topic or DEFAULT_TOPICS),
                            max_repos=args.max_repos, max_skills=args.max_skills,
                            sort=args.sort)
        print(json.dumps(out))
    elif args.cmd == "ingest-repos":
        init_db(engine)
        print(f"enqueued {ingest_repos(engine, args.repos, args.max_skills)} new artifacts")
    elif args.cmd == "run":
        out = run(engine, batch=args.batch, forever=args.forever,
                  fake=True if args.fake else None, concurrency=args.concurrency,
                  max_usd_day=args.max_usd_day, quiet=args.quiet)
        print(f"done: scored={out['scored']} failed={out['failed']}"
              + (" (daily cap reached)" if out["capped"] else ""))
    elif args.cmd == "requeue":
        init_db(engine)
        print(f"requeued {requeue(engine, args.decision or ['escalate', 'block'])} artifacts")
    elif args.cmd == "prune-tests":
        print(json.dumps(prune_tests(engine, apply=args.yes)))
    elif args.cmd == "rethreshold":
        init_db(engine)
        print(json.dumps(rethreshold(engine)))
    elif args.cmd == "backfill-meta":
        init_db(engine)
        print(f"updated {backfill_meta(engine)} artifacts")
    elif args.cmd == "stats":
        print(json.dumps(stats(engine), indent=2, default=str))
    elif args.cmd == "export-catalog":
        n = export_catalog(engine, Path(args.out).expanduser())
        print(f"wrote {n} items to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
