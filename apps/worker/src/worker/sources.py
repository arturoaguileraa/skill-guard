"""Bulk sources. GitHub repo-tree crawling: one API call lists every SKILL.md in a
repo, so it scales far past code search's 1,000-result cap. Everything funnels into `store.enqueue`, which dedupes by content hash,
so re-running any source is cheap and idempotent."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

import httpx
from sqlalchemy import select
from sqlalchemy.engine import Engine

from worker.db import artifacts
from worker.meta import is_test_path
from worker.store import enqueue

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

MIN_CHARS = 80  # skip empty/placeholder SKILL.md files
MAX_BYTES = 200_000
DEFAULT_TOPICS = (
    "agent-skills", "claude-skills", "claude-code-skills", "claude-skill",
    "anthropic-skills", "agent-skill", "ai-agent-skills", "skills",
)


class GitHub:
    """Tiny GitHub client that sleeps through primary/secondary rate limits."""

    def __init__(self, token: str | None = None):
        token = token or os.environ.get("GITHUB_TOKEN")
        if not token:
            raise RuntimeError("GITHUB_TOKEN required for GitHub sources")
        self.c = httpx.Client(timeout=30, headers={
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def get(self, url: str, **kw) -> httpx.Response:
        for _ in range(6):
            r = self.c.get(url, **kw)
            limited = r.status_code == 429 or (
                r.status_code == 403
                and (r.headers.get("x-ratelimit-remaining") == "0"
                     or "retry-after" in r.headers or "rate limit" in r.text.lower())
            )
            if not limited:
                return r
            reset = int(r.headers.get("x-ratelimit-reset", "0")) - int(time.time())
            wait = int(r.headers.get("retry-after", 0)) or max(5, min(reset + 2, 3700))
            print(f"  github rate limit, sleeping {wait}s")
            time.sleep(wait)
        return r


def _known_repo(engine: Engine, repo: str) -> bool:
    with engine.begin() as conn:
        return conn.execute(
            select(artifacts.c.hash).where(artifacts.c.repo == repo).limit(1)
        ).first() is not None


def ingest_repo(engine: Engine, gh: GitHub, repo: str, max_skills: int = 200) -> int:
    """Enqueue every SKILL.md in a repo at its current HEAD commit. Returns new count."""
    r = gh.get(f"{API}/repos/{repo}/commits/HEAD",
               headers={"Accept": "application/vnd.github.sha"})
    if r.status_code != 200:
        return 0  # empty, renamed, or private repo
    sha = r.text.strip()
    t = gh.get(f"{API}/repos/{repo}/git/trees/{sha}", params={"recursive": "1"})
    if t.status_code != 200:
        return 0
    paths = [
        x["path"] for x in t.json().get("tree", [])
        if x.get("type") == "blob"
        and x["path"].rsplit("/", 1)[-1].lower() == "skill.md"
        and int(x.get("size") or 0) <= MAX_BYTES
        and not is_test_path(x["path"])
    ][:max_skills]
    if not paths:
        return 0

    def fetch(path: str) -> tuple[str, str | None]:
        try:
            resp = httpx.get(f"{RAW}/{repo}/{sha}/{path}", timeout=30)
            return path, resp.text if resp.status_code == 200 else None
        except httpx.HTTPError:
            return path, None

    new = 0
    with ThreadPoolExecutor(8) as pool:
        for path, body in pool.map(fetch, paths):
            if not body or len(body.strip()) < MIN_CHARS:
                continue
            _, is_new = enqueue(
                engine, content=body, source="github-repo",
                source_url=f"https://github.com/{repo}/blob/{sha}/{path}",
                identity=repo, kind="skill", repo=repo, path=path)
            new += int(is_new)
    return new


def discover_repos(gh: GitHub, query: str, max_repos: int,
                   sort: str = "stars") -> Iterator[str]:
    """Repo search (1,000-result cap per query, 100/page)."""
    seen = 0
    for page in range(1, 11):
        if seen >= max_repos:
            return
        r = gh.get(f"{API}/search/repositories", params={
            "q": query, "sort": sort, "order": "desc",
            "per_page": min(100, max_repos - seen), "page": page})
        if r.status_code != 200:
            return
        items = r.json().get("items", [])
        if not items:
            return
        for it in items:
            seen += 1
            yield it["full_name"]
        time.sleep(2.5)  # search API: 30 req/min


def ingest_topics(engine: Engine, topics=DEFAULT_TOPICS, max_repos: int = 200,
                  max_skills: int = 200, sort: str = "stars",
                  parallel: int = 6) -> dict:
    """Discover repos per topic, then crawl several repos at once (big trees are
    slow; the work is I/O-bound and enqueue is idempotent, so this is safe)."""
    gh = GitHub()
    totals = {"repos_crawled": 0, "repos_skipped": 0, "new_skills": 0}
    seen: set[str] = set()
    for topic in topics:
        found = [r for r in discover_repos(gh, f"topic:{topic}", max_repos, sort)
                 if r not in seen]
        seen.update(found)
        todo = [r for r in found if not _known_repo(engine, r)]
        totals["repos_skipped"] += len(found) - len(todo)
        print(f"topic:{topic}: {len(found)} repos, {len(todo)} new", flush=True)

        def crawl(repo: str) -> tuple[str, int]:
            try:
                return repo, ingest_repo(engine, gh, repo, max_skills)
            except Exception as exc:  # noqa: BLE001 - one bad repo must not stop the crawl
                print(f"  {repo}: skipped ({type(exc).__name__}: {exc})", flush=True)
                return repo, 0

        with ThreadPoolExecutor(parallel) as pool:
            for repo, n in pool.map(crawl, todo):
                totals["repos_crawled"] += 1
                totals["new_skills"] += n
                if n:
                    print(f"  {repo}: +{n}", flush=True)
    return totals


def ingest_repos(engine: Engine, repos: list[str], max_skills: int = 200) -> int:
    gh = GitHub()
    return sum(ingest_repo(engine, gh, r, max_skills) for r in repos)
