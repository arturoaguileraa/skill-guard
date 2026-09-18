"""Repository: enqueue artifacts, claim jobs, persist results. Idempotent by
content hash. The queue is a Postgres table using SELECT ... FOR UPDATE SKIP
LOCKED so many workers can pull safely; on SQLite (single-worker dev) it
degrades to a plain transaction."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from worker.db import artifacts, jobs, results
from worker.meta import parse_frontmatter, parse_github_url


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
                        "ORDER BY created_at LIMIT :n FOR UPDATE SKIP LOCKED"
                    ),
                    {"n": batch},
                )
            ]
        else:
            ids = [
                r[0]
                for r in conn.execute(
                    select(jobs.c.id).where(jobs.c.status == "pending")
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
