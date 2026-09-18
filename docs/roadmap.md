# Roadmap — next steps

Proposals, **not decisions**. Each item becomes an ADR (`docs/adr/`) when it is picked up.

## Constraint that shapes everything: latency

The live tester's first verdict must not get slower ([ADR-0005](adr/0005-instant-provisional-and-latency.md): ~0.5s per Jev call, content-hash cache, real→real dial). Rule for every item below:

> Nothing that touches the network or adds Jev calls may block the first verdict.

- **Inline (allowed):** pure-CPU deterministic work — URL/host extraction, allowlist lookup, cheap pattern matches (`postinstall`, `curl | bash`, base64).
- **Parallel:** extra Jev calls for extra files run concurrently, so latency is the slowest file, not the sum. The content-hash cache means an edit only re-scores the file that changed.
- **Background:** anything with network I/O (fetching remote pages) goes through a queue. The first verdict ships immediately; a later result arrives as a second *real* reading (never an invented intermediate number).

## 1. Multi-file skills (do first)

**The gap, measured.** Today the playground and the worker score only the text of `SKILL.md`; the CLI (`skill-guard scan <dir>`) also reads bundled scripts. Against the public Snyk `toxicskills-goof` samples and the fixtures of its `skillguard` zip:

- With the whole folder, Jev blocked 12 of 13 attack fixtures and allowed the 2 clean ones.
- The miss was `evasive-11-polyglot-json`: the payload lives in a `config-template.json` (`postinstall: curl … | bash`, exfiltration of the agent config), and the JSON is not read as a script.
- Text-only scoring makes the same fixtures look benign, because the attack is not in `SKILL.md`. In the hub, `skill-defender` is benign (0.35) from its text but suspicious (0.57) when scanned as a folder.

**Proposal.** The artifact is the skill *directory*, not `SKILL.md`.

- **Ingest:** the worker already pins a commit SHA per repo; fetch the whole skill tree at that SHA, with caps on file count and size.
- **What to read:** files linked from `SKILL.md` first, plus scripts, `hooks/`, and manifests/JSON that carry `scripts` — the case that failed.
- **Skip cheaply:** images, lockfiles, binaries — deterministic rules, no Jev call.
- **Score per file, aggregate:** overall risk = worst file (or the existing noisy-OR over files). Keep the "description vs. what the code does" check (`capability_beyond_purpose`) across files.
- **Store and show per-file results**, so the hub can say *where* the attack is (`scripts/setup.sh`) instead of just "malicious".
- **Playground:** tabs to paste several files.
- **Tests:** the 15 Snyk fixtures (13 attacks, 2 clean) become a regression set; `evasive-11` is the case that must turn green.

Open questions: per-file vs. bundle-level hashing in the DB schema (`artifacts.hash`); Jev context limits on large files (chunking); how to weight a bundled file that `SKILL.md` never references.

## 2. Skills that point at remote content

**The case.** A skill whose own text is benign says "for more info, see `prettier.gerd.com`", and that page carries the malicious instructions. The text is clean; the risk is delegated to content that can change at any time. Remote text is as untrusted as the artifact (ADR-0001); Jev cannot be talked into anything, but the *agent* could.

Three tiers, cheapest first:

1. **Extract and floor (inline, no fetching).** Pull every URL/host from the text and scripts deterministically. Show them in the verdict. If the skill tells the agent to follow instructions from an unknown host, the verdict is **at least suspicious** ("delegates to remote content we cannot verify"). Builds on the existing `unpinned_remote_source` / `fetch_and_execute` questions.
2. **Trusted hosts.** An allowlist (e.g. GitHub raw pinned to a commit SHA, well-known vendor docs) does not raise the floor; an unknown domain does.
3. **Fetch and score (background).** Download the linked page and score it as a child artifact through Jev; the skill's verdict is the worst of skill and pages. Requirements:
   - Safe fetcher: no credentials, no JavaScript, size and time caps, block internal addresses (SSRF: `169.254.*`, `localhost`).
   - Depth of 1–2 hops and a cost cap.
   - **Cloaking:** a site can show clean text to scanners and something else to agents. Fetch with several identities and compare.
   - **Changes after the scan:** the result is valid only for the content fetched. Store the content hash, re-scan periodically, and let the verdict expire.
   - Cache by URL with a TTL.

Tier 1–2 need no new infrastructure. Tier 3 needs the background queue and depends on multi-file (a linked page is another file of the artifact).

## Suggested order

1. Multi-file artifacts (closes a measured miss; prerequisite for 2.3).
2. URL extraction and the suspicious floor for unknown hosts (2.1, 2.2).
3. Background fetch-and-score with hash pinning and expiry (2.3).
