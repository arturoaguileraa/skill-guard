"""The worker loop: claim a batch of pending jobs, score them, persist. Safe to
run many replicas against Postgres (SKIP LOCKED). Stops when the queue drains
(unless --forever), so it works both as a one-shot batch job and a daemon."""

from __future__ import annotations

import time

from sqlalchemy.engine import Engine

from worker.scorer import Scorer
from worker.store import claim, complete, fail


def run(engine: Engine, *, batch: int = 8, forever: bool = False,
        idle_sleep: float = 5.0, fake: bool | None = None) -> dict:
    scorer = Scorer(fake=fake)
    done = failed = 0
    while True:
        jobs = claim(engine, batch=batch)
        if not jobs:
            if forever:
                time.sleep(idle_sleep)
                continue
            break
        for job in jobs:
            try:
                result = scorer.score_text(job.content, job.identity)
                complete(engine, job, result)
                done += 1
                print(f"  ✓ {job.identity or job.artifact_hash[:12]} "
                      f"-> {result['decision']} {result['risk']:.2f}")
            except Exception as exc:  # noqa: BLE001 - worker must not die on one job
                fail(engine, job, f"{type(exc).__name__}: {exc}")
                failed += 1
                print(f"  ✗ {job.identity or job.artifact_hash[:12]}: {exc}")
    return {"scored": done, "failed": failed}
