"""The worker loop: claim a batch of pending jobs, score them concurrently,
persist. Safe to run many replicas against Postgres (SKIP LOCKED). Stops when the
queue drains (unless --forever), so it works as a one-shot job and as a daemon.
A daily spend cap (shared through the DB) stops scoring before it can run away."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.engine import Engine

from worker.scorer import Scorer
from worker.store import claim, complete, fail, spend_today

DEFAULT_MAX_USD_DAY = 5.0


def daily_cap(override: float | None) -> float:
    if override is not None:
        return override
    return float(os.environ.get("WORKER_MAX_USD_PER_DAY", DEFAULT_MAX_USD_DAY))


def run(engine: Engine, *, batch: int = 16, forever: bool = False,
        idle_sleep: float = 5.0, fake: bool | None = None,
        concurrency: int = 8, max_usd_day: float | None = None,
        quiet: bool = False) -> dict:
    scorer = Scorer(fake=fake)
    cap = daily_cap(max_usd_day)  # <= 0 disables the cap
    done = failed = 0
    capped = False
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        while True:
            if cap > 0 and not scorer.is_fake:
                spent = spend_today(engine)
                if spent >= cap:
                    capped = True
                    print(f"daily spend cap reached (${spent:.3f} >= ${cap:.2f}); "
                          "not scoring more today")
                    if forever:
                        time.sleep(300)
                        continue
                    break
            jobs = claim(engine, batch=batch)
            if not jobs:
                if forever:
                    time.sleep(idle_sleep)
                    continue
                break
            # Score AND persist inside the worker threads: Neon round-trips are
            # the slow part, so they must overlap too.
            def process(job):
                label = job.identity or job.artifact_hash[:12]
                try:
                    result = scorer.score_text(job.content, job.identity)
                    complete(engine, job, result)
                    return label, result, None
                except Exception as exc:  # noqa: BLE001 - one job must not kill the worker
                    fail(engine, job, f"{type(exc).__name__}: {exc}")
                    return label, None, exc

            for label, result, exc in pool.map(process, jobs):
                if exc is None:
                    done += 1
                    if not quiet:
                        print(f"  ok {label} -> {result['decision']} {result['risk']:.2f}")
                else:
                    failed += 1
                    print(f"  FAIL {label}: {exc}")
            if quiet and done % 200 < len(jobs):
                print(f"  scored={done} failed={failed} spend_today=${spend_today(engine):.3f}")
    return {"scored": done, "failed": failed, "capped": capped}
