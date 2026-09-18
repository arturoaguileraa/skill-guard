"""Artifact model: the unit of analysis, and the `state` we hand to Jev.

An Artifact is whatever an agent might load and obey -- a Claude Code skill, an
MCP server definition, a plugin hook. Extraction is deterministic and does no
judging: it decides *what the model gets to see*, never *what it means*.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

ArtifactKind = Literal["skill", "mcp_server", "hook"]

# Jev degrades on large irrelevant state (see docs: model jaggedness), so every
# free-text field is capped. Instruction text is the payload we actually care
# about, so it gets the largest budget.
MAX_INSTRUCTIONS_CHARS = 24_000
MAX_SCRIPT_CHARS = 8_000
MAX_SCRIPTS = 6


@dataclass
class Artifact:
    """One analyzable unit, already reduced to text."""

    kind: ArtifactKind
    identity: str
    source: str
    declared: dict[str, Any] = field(default_factory=dict)
    instructions: str = ""
    bundled_files: list[dict[str, str]] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)

    def to_state(self) -> dict[str, Any]:
        """Render as Jev `state`.

        Deliberately an object, not a blob: named parts let a question scope
        itself to one part ("in the instructions, ...") instead of the whole
        artifact. Computed facts live under their own key so the model is never
        asked to count or compare numbers -- code already did that.
        """
        return {
            "artifact_kind": self.kind,
            "identity": self.identity,
            "declared_metadata": self.declared,
            "instructions_text": _clip(self.instructions, MAX_INSTRUCTIONS_CHARS),
            "bundled_files": self.bundled_files[:MAX_SCRIPTS],
            "computed_facts": self.facts,
        }

    def state_size(self) -> int:
        return len(json.dumps(self.to_state()))


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = limit * 2 // 3
    tail = limit - head
    return f"{text[:head]}\n\n[... {len(text) - limit} chars elided ...]\n\n{text[-tail:]}"


def read_text(path: Path, limit: int = MAX_SCRIPT_CHARS) -> str:
    try:
        return _clip(path.read_text(encoding="utf-8", errors="replace"), limit)
    except OSError:
        return ""
