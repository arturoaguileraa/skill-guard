# 0003 — Target agent skills / MCP servers first

**Status:** Accepted

## Context

The engine could triage several artifact classes: language packages (npm/PyPI), compiled binaries (ELF/PE/Mach-O), and agent-facing artifacts (Claude Code skills, MCP servers). Each needs a different extraction layer. We wanted the shortest path to validating the core hypothesis (that a System One model gives calibrated, injection-resistant triage).

## Decision

Ship v1 for **skills and MCP servers**.

## Consequences

- **Positive:** They are text-only (frontmatter + markdown, or a JSON config), so extraction is lightweight — no disassembly toolchain. Nobody covers this class yet. It exercises the whole pipeline end-to-end quickly, so calibration and adversarial numbers arrive in days.
- **Negative:** Narrower than a package/binary scanner; the corpus of labeled malicious *skills* barely exists in the wild, so fixtures are synthetic-but-grounded ([ADR-0006](0006-static-synthetic-hub-catalog.md)).
- **Deferred:** Binaries — the extraction layer (Ghidra/`capa`/radare2) is a project in itself and would block validation of the central hypothesis. Packages — a natural second target with public labeled datasets.
