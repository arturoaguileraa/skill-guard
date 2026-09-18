"""Feed the queue. Two sources: local files/dirs (for backfill and testing) and
GitHub code search (for scale). Everything is deduped by content hash in the
store, so re-running is cheap and idempotent."""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
from sqlalchemy.engine import Engine

from worker.store import enqueue

GITHUB_API = "https://api.github.com"


def ingest_paths(engine: Engine, paths: list[Path]) -> int:
    """Enqueue every SKILL.md found under the given files/dirs."""
    n = 0
    for base in paths:
        files = [base] if base.is_file() else base.rglob("SKILL.md")
        for f in files:
            if f.name != "SKILL.md":
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            _, new = enqueue(
                engine, content=content, source="local",
                source_url=str(f), identity=f.parent.name, kind="skill")
            n += int(new)
    return n


def ingest_github(engine: Engine, query: str = "filename:SKILL.md",
                  max_results: int = 100, per_page: int = 50) -> int:
    """Discover skills via GitHub code search and enqueue their contents.

    Requires GITHUB_TOKEN. Code search is rate-limited (~10 req/min), so we page
    politely and back off on 403/rate-limit.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN required for GitHub ingestion")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.text-match+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    enqueued = 0
    seen_pages = (max_results + per_page - 1) // per_page
    with httpx.Client(headers=headers, timeout=30) as client:
        for page in range(1, seen_pages + 1):
            resp = client.get(
                f"{GITHUB_API}/search/code",
                params={"q": query, "per_page": per_page, "page": page},
            )
            if resp.status_code == 403:  # rate limited
                reset = int(resp.headers.get("x-ratelimit-reset", "0"))
                wait = max(5, reset - int(time.time()))
                print(f"  rate limited, sleeping {wait}s")
                time.sleep(wait)
                resp = client.get(
                    f"{GITHUB_API}/search/code",
                    params={"q": query, "per_page": per_page, "page": page})
            resp.raise_for_status()
            items = resp.json().get("items", [])
            if not items:
                break
            for it in items:
                raw = _raw_url(it)
                if not raw:
                    continue
                try:
                    body = client.get(raw).text
                except httpx.HTTPError:
                    continue
                _, new = enqueue(
                    engine, content=body, source="github",
                    source_url=it.get("html_url"),
                    identity=it.get("repository", {}).get("full_name"),
                    kind="skill")
                enqueued += int(new)
            time.sleep(6)  # stay under the code-search rate limit
    return enqueued


def _raw_url(item: dict) -> str | None:
    repo = item.get("repository", {}).get("full_name")
    path = item.get("path")
    if not repo or not path:
        return None
    # default branch is not in the search payload; raw.githubusercontent resolves HEAD
    return f"https://raw.githubusercontent.com/{repo}/HEAD/{path}"
