# Architecture Decision Records

Short records of the decisions that shaped skillguard and their trade-offs. Each is immutable once accepted; supersede rather than rewrite.

| # | Decision | Status |
|---|---|---|
| [0001](0001-system-one-over-llm.md) | Use a System One model (Jev), not an LLM, for triage | Accepted |
| [0002](0002-microservice-monorepo-boundary.md) | Isolate Jev in a Python microservice; monorepo with a TS↔Jev boundary | Accepted |
| [0003](0003-skills-mcp-first-target.md) | Target agent skills / MCP servers first (not binaries or packages) | Accepted |
| [0004](0004-scoring-and-weights.md) | Confidence-weighted noisy-OR aggregation with tuned family weights | Accepted |
| [0005](0005-instant-provisional-and-latency.md) | Instant heuristic preview + warm pool + cache; the real→real invariant | Accepted |
| [0006](0006-static-synthetic-hub-catalog.md) | The hub is a static catalog of synthetic-but-grounded fixtures | Accepted |
| [0007](0007-awwwards-design-system.md) | awwwards-grade design system: grotesk + mono, monochrome + risk color | Accepted |
| [0008](0008-mass-analysis-worker.md) | Mass-analysis worker + database-backed catalog (Neon, SKIP LOCKED queue) | Accepted |
