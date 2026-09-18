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
from worker.store import stats


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

    pr = sub.add_parser("run", help="score pending jobs")
    pr.add_argument("--batch", type=int, default=8)
    pr.add_argument("--forever", action="store_true")
    pr.add_argument("--fake", action="store_true", help="force the heuristic client")

    sub.add_parser("stats", help="queue + result counts")

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
    elif args.cmd == "run":
        out = run(engine, batch=args.batch, forever=args.forever,
                  fake=True if args.fake else None)
        print(f"done: scored={out['scored']} failed={out['failed']}")
    elif args.cmd == "stats":
        print(json.dumps(stats(engine), indent=2, default=str))
    elif args.cmd == "export-catalog":
        n = export_catalog(engine, Path(args.out).expanduser())
        print(f"wrote {n} items to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
