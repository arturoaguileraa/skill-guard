"""Repository: enqueue artifacts, claim jobs, persist results. Idempotent by
content hash. The queue is a Postgres table using SELECT ... FOR UPDATE SKIP
LOCKED so many workers can pull safely; on SQLite (single-worker dev) it
degrades to a plain transaction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from worker.db import artifacts, jobs, results
from worker.meta import parse_frontmatter, parse_github_url


# A job stuck in `running` longer than this belongs to a crashed worker: reclaim it.
STALE_MINUTES = 10


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class Claimed:
    job_id: int
    artifact_hash: str
    content: str
    identity: str | None
    kind: str | None


def enqueue(
    engine: Engine,
    *,
    content: str,
    source: str,
    source_url: str | None = None,
    identity: str | None = None,
    kind: str = "skill",
    repo: str | None = None,
    path: str | None = None,
) -> tuple[str, bool]:
    """Upsert the artifact and create a pending job if none is outstanding.
    Returns (hash, was_new)."""
    h = content_hash(content)
    name, description = parse_frontmatter(content)
    if repo is None:
        repo, path = parse_github_url(source_url)
    meta = {"repo": repo, "path": path, "name": name, "description": description}
    is_pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        row = {
            "hash": h, "source": source, "source_url": source_url,
            "identity": identity, "kind": kind, "content": content,
            "updated_at": datetime.now(timezone.utc), **meta,
        }
        if is_pg:
            stmt = pg_insert(artifacts).values(**row).on_conflict_do_update(
                index_elements=["hash"],
                set_={"source_url": source_url, "identity": identity,
                       "updated_at": row["updated_at"], **meta},
            )
            conn.execute(stmt)
        else:
            exists = conn.execute(
                select(artifacts.c.hash).where(artifacts.c.hash == h)
            ).first()
            if exists:
                conn.execute(update(artifacts).where(artifacts.c.hash == h).values(
                    source_url=source_url, identity=identity,
                    updated_at=row["updated_at"], **meta))
            else:
                conn.execute(insert(artifacts).values(**row))

        # already scored, or a job already queued/running? don't re-enqueue.
        scored = conn.execute(
            select(results.c.artifact_hash).where(results.c.artifact_hash == h)
        ).first()
        pending = conn.execute(
            select(jobs.c.id).where(
                jobs.c.artifact_hash == h,
                jobs.c.status.in_(("pending", "running")),
            )
        ).first()
        if scored or pending:
            return h, False
        conn.execute(insert(jobs).values(artifact_hash=h, status="pending"))
        return h, True


def claim(engine: Engine, batch: int = 8) -> list[Claimed]:
    """Atomically claim up to `batch` pending jobs and mark them running."""
    is_pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        if is_pg:
            ids = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT id FROM jobs WHERE status='pending' "
                        f"OR (status='running' AND locked_at < now() - interval '{STALE_MINUTES} minutes') "
                        "ORDER BY created_at LIMIT :n FOR UPDATE SKIP LOCKED"
                    ),
                    {"n": batch},
                )
            ]
        else:
            ids = [
                r[0]
                for r in conn.execute(
                    select(jobs.c.id).where(
                        (jobs.c.status == "pending")
                        | ((jobs.c.status == "running")
                           & (jobs.c.locked_at < datetime.now(timezone.utc).replace(tzinfo=None)
                              - timedelta(minutes=STALE_MINUTES))))
                    .order_by(jobs.c.created_at).limit(batch)
                )
            ]
        if not ids:
            return []
        conn.execute(
            update(jobs).where(jobs.c.id.in_(ids)).values(
                status="running", locked_at=datetime.now(timezone.utc),
                attempts=jobs.c.attempts + 1)
        )
        rows = conn.execute(
            select(jobs.c.id, jobs.c.artifact_hash, artifacts.c.content,
                   artifacts.c.identity, artifacts.c.kind)
            .join(artifacts, artifacts.c.hash == jobs.c.artifact_hash)
            .where(jobs.c.id.in_(ids))
        ).all()
        return [Claimed(*r) for r in rows]


def complete(engine: Engine, claimed: Claimed, result: dict) -> None:
    is_pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        payload = {"artifact_hash": claimed.artifact_hash, **result}
        if is_pg:
            conn.execute(
                pg_insert(results).values(**payload).on_conflict_do_update(
                    index_elements=["artifact_hash"],
                    set_={**result, "scored_at": datetime.now(timezone.utc)},
                )
            )
        else:
            conn.execute(results.delete().where(
                results.c.artifact_hash == claimed.artifact_hash))
            conn.execute(insert(results).values(**payload))
        conn.execute(update(jobs).where(jobs.c.id == claimed.job_id).values(
            status="done", error=None, updated_at=datetime.now(timezone.utc)))


def fail(engine: Engine, claimed: Claimed, err: str, max_attempts: int = 3) -> None:
    """Requeue for another attempt, or dead-letter to `error` past the cap."""
    with engine.begin() as conn:
        attempts = conn.execute(
            select(jobs.c.attempts).where(jobs.c.id == claimed.job_id)
        ).scalar() or 0
        status = "pending" if attempts < max_attempts else "error"
        conn.execute(
            update(jobs).where(jobs.c.id == claimed.job_id).values(
                status=status, error=err[:2000],
                updated_at=datetime.now(timezone.utc))
        )


def stats(engine: Engine) -> dict:
    with engine.begin() as conn:
        by_status = dict(
            conn.execute(
                select(jobs.c.status, func.count()).group_by(jobs.c.status)
            ).all()
        )
        by_decision = dict(
            conn.execute(
                select(results.c.decision, func.count()).group_by(results.c.decision)
            ).all()
        )
        n_art = conn.execute(select(func.count()).select_from(artifacts)).scalar()
    return {"artifacts": n_art, "jobs": by_status, "results": by_decision}


def backfill_meta(engine: Engine) -> int:
    """Fill repo/path/name/description for rows ingested before those columns
    existed. Deterministic and offline: parses stored content and source_url."""
    n = 0
    with engine.begin() as conn:
        rows = conn.execute(
            select(artifacts.c.hash, artifacts.c.content, artifacts.c.source_url)
            .where(artifacts.c.name.is_(None) & artifacts.c.repo.is_(None))
        ).all()
        for r in rows:
            name, description = parse_frontmatter(r.content)
            repo, path = parse_github_url(r.source_url)
            if not (name or description or repo):
                continue
            conn.execute(update(artifacts).where(artifacts.c.hash == r.hash).values(
                name=name, description=description, repo=repo, path=path))
            n += 1
    return n


def spend_today(engine: Engine) -> float:
    """Jev spend so far today (UTC), from the results table — shared by every
    worker replica, so a daily cap holds globally."""
    midnight = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    with engine.begin() as conn:
        return float(conn.execute(
            select(func.coalesce(func.sum(results.c.cost_usd), 0.0))
            .where(results.c.scored_at >= midnight)
        ).scalar() or 0.0)


def rethreshold(engine: Engine) -> dict:
    """Re-decide every stored result from its stored risk under the engine's
    current thresholds. Zero Jev calls: decisions are a pure function of the
    risk, the mean confidence and the integrity warning we already saved."""
    from skillguard.bank import load_bank
    from skillguard.score import Thresholds, decide

    th = Thresholds()
    dq = [q for q, s in load_bank().specs.items() if s.deception]
    changed: dict[str, int] = {}
    with engine.begin() as conn:
        rows = conn.execute(select(
            results.c.artifact_hash, results.c.risk, results.c.mean_confidence,
            results.c.integrity_warning, results.c.decision,
            results.c.readings)).all()
        for r in rows:
            # Rows scored before readings were stored have no deception evidence to
            # judge: leave the gate off for them rather than guess.
            dec = None
            if r.readings:
                dec = max((v["v"] * v["c"] for q, v in r.readings.items() if q in dq),
                          default=0.0)
            new, _ = decide(r.risk, r.mean_confidence or 0.0, r.integrity_warning, th, dec)
            if new.value != r.decision:
                key = f"{r.decision}->{new.value}"
                changed[key] = changed.get(key, 0) + 1
                conn.execute(update(results).where(
                    results.c.artifact_hash == r.artifact_hash).values(decision=new.value))
    return {"rows": len(rows), "review_threshold": th.review, "changed": changed}


def requeue(engine: Engine, decisions: list[str]) -> int:
    """Send already-scored artifacts back through the queue (e.g. after the
    question bank changed). Results are overwritten when the new score lands."""
    with engine.begin() as conn:
        hashes = [r[0] for r in conn.execute(
            select(results.c.artifact_hash).where(results.c.decision.in_(decisions)))]
        busy = {r[0] for r in conn.execute(
            select(jobs.c.artifact_hash).where(jobs.c.status.in_(("pending", "running"))))}
        todo = [h for h in hashes if h not in busy]
        if todo:  # one batched INSERT: a round-trip per row is painfully slow on Neon
            conn.execute(insert(jobs), [{"artifact_hash": h, "status": "pending"} for h in todo])
    return len(todo)


def prune_tests(engine: Engine, apply: bool = False) -> dict:
    """Find (and with apply=True delete) artifacts that live under test/fixture
    paths. Dry run by default."""
    from worker.meta import is_test_path

    with engine.begin() as conn:
        rows = conn.execute(select(artifacts.c.hash, artifacts.c.repo, artifacts.c.path)).all()
        hit = [r for r in rows if is_test_path(r.path)]
        if apply and hit:
            hs = [r.hash for r in hit]
            for t, col in ((results, results.c.artifact_hash), (jobs, jobs.c.artifact_hash),
                           (artifacts, artifacts.c.hash)):
                conn.execute(t.delete().where(col.in_(hs)))
    return {"matched": len(hit), "deleted": len(hit) if apply else 0,
            "by_repo": {r: sum(1 for x in hit if x.repo == r) for r in {x.repo for x in hit}}}
