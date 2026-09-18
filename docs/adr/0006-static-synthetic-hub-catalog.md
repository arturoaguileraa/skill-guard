# 0006 — The hub is a static catalog of synthetic-but-grounded fixtures

**Status:** Accepted — superseded in production by [ADR-0009](0009-vercel-services-and-db-backed-hub.md); still the no-database fallback and the demo corpus

## Context

The hub (`/hub`) lets someone check whether a skill they might install is malware — a catalog of "what we've analyzed" with verdicts. But the corpus is 68 synthetic fixtures. Listing real third-party skills by name with a "malware" verdict we haven't genuinely vetted would be misleading — fabricated records presented as authoritative.

## Decision

- Generate the catalog **offline** from the cached Jev readings: `eval/build_catalog.py` re-scores the labeled fixtures with the current weights and writes `eval/catalog.json` (0 API calls). The Jev service serves it at `GET /catalog`, reached through the same oRPC boundary as `analyze`.
- Every entry is flagged `synthetic: true`, and the hub shows a prominent disclaimer: a demo corpus of synthetic-but-grounded test artifacts, not an authoritative verdict on any real published skill.

## Consequences

- **Positive:** Honest — it demonstrates how triage behaves without pretending to be a registry. Fast and free (static data, no live calls). Consistent architecture (server→jev boundary reused). Regenerating after a corpus/weight change is one command.
- **Negative:** Not live — the catalog reflects the fixtures at build time, not real-world skills. A real public "is this skill safe" registry would need vetted real artifacts and a submission/ re-scoring pipeline — deliberately out of scope for now.
