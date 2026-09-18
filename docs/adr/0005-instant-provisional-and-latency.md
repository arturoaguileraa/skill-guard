# 0005 — Instant heuristic preview, warm pool, cache, and the real→real invariant

**Status:** Accepted

## Context

The live tester re-scores on every edit. Measured latency: the Jev call is essentially all of it — ~455ms warm, ~890ms cold (a 2x connection cliff); our server→jev hop is ~10ms (noise). Perceived latency was ~900ms (450ms debounce + Jev). A naive UI also flashed a wrong intermediate value on every keystroke.

## Decision

Attack perceived latency and the flash, not the (near-floor) Jev call:

1. **Instant client-side heuristic** (`apps/web/src/lib/provisional.ts`) — a TS port of the deterministic facts layer, ~0.5ms, shown on the very first paint only.
2. **real→real invariant** — once Jev has answered, always show a real reading: `view = calibrated ?? preview`, with `keepPreviousData` holding the last real reading (dimmed, "re-analyzing…") while a new one loads. The dial moves real→real and never jumps to a heuristic number on edit.
3. **Warm connection** — `service.py` lifespan warms the Jev connection at startup and pings every 30s, removing the cold cliff.
4. **Content-hash cache** in the Jev service — identical snapshots (revert, re-type) return in ~2ms.
5. Debounce lowered 450ms → 180ms; TanStack Query cancels superseded in-flight requests.

## Consequences

- **Positive:** Feedback feels instant (~0.5ms provisional); calibrated readings land ~450ms warm; repeats ~2ms. No jarring flash. Also tells the value story honestly: fast heuristic → calibrated model.
- **Negative:** The provisional heuristic duplicates a subset of the extraction logic in TS (kept minimal, clearly labeled "heuristic preview"). The real→real logic is subtle — see the invariant note in `CLAUDE.md`; don't regress it.
