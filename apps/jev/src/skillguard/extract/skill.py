"""Turn a Claude Code skill directory into an Artifact."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from skillguard.artifact import MAX_SCRIPTS, Artifact, read_text
from skillguard.extract.facts import compute

SCRIPT_SUFFIXES = {".sh", ".bash", ".zsh", ".py", ".js", ".ts", ".mjs", ".rb", ".pl", ".ps1"}
DOC_SUFFIXES = {".md", ".txt", ".rst"}


def find_skills(root: Path) -> list[Path]:
    """Every directory under `root` holding a SKILL.md, deduped by real path."""
    seen: dict[Path, Path] = {}
    for skill_md in sorted(root.rglob("SKILL.md", recurse_symlinks=True)):
        try:
            real = skill_md.resolve()
        except OSError:
            continue
        seen.setdefault(real, skill_md)
    return [p.parent for p in seen.values()]


def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), parts[2].lstrip("\n")


def extract_skill(skill_dir: Path) -> Artifact:
    skill_md = skill_dir / "SKILL.md"
    raw = read_text(skill_md, limit=200_000)
    declared, body = _split_frontmatter(raw)

    bundled: list[dict[str, str]] = []
    corpus = [body]
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path.name == "SKILL.md":
            continue
        suffix = path.suffix.lower()
        if suffix not in SCRIPT_SUFFIXES | DOC_SUFFIXES:
            continue
        content = read_text(path)
        corpus.append(content)
        if len(bundled) < MAX_SCRIPTS:
            bundled.append({
                "path": str(path.relative_to(skill_dir)),
                "executable": path.stat().st_mode & 0o111 != 0,
                "kind": "script" if suffix in SCRIPT_SUFFIXES else "doc",
                "content": content,
            })

    facts = compute("\n".join(corpus), extra={
        "bundled_script_count": sum(1 for b in bundled if b["kind"] == "script"),
        "executable_file_count": sum(1 for b in bundled if b["executable"]),
        "declares_allowed_tools": "allowed-tools" in declared or "allowed_tools" in declared,
        "declared_allowed_tools": declared.get("allowed-tools") or declared.get("allowed_tools"),
    })

    return Artifact(
        kind="skill",
        identity=str(declared.get("name") or skill_dir.name),
        source=str(skill_dir),
        declared=declared,
        instructions=body,
        bundled_files=bundled,
        facts=facts,
    )


def artifact_from_text(raw: str, identity: str | None = None) -> "Artifact":
    """Build an Artifact from a pasted SKILL.md string, no files on disk.

    Used by the live analyzer: the editor's whole buffer is the artifact. We
    split frontmatter, then compute facts over the body so the deterministic
    signals (paths, hosts, encoded blobs) are present exactly as in a real scan.
    """
    declared, body = _split_frontmatter(raw)
    facts = compute(body, extra={
        "declares_allowed_tools": "allowed-tools" in declared or "allowed_tools" in declared,
        "declared_allowed_tools": declared.get("allowed-tools") or declared.get("allowed_tools"),
    })
    return Artifact(
        kind="skill",
        identity=str(identity or declared.get("name") or "pasted-skill"),
        source="editor",
        declared=declared,
        instructions=body,
        bundled_files=[],
        facts=facts,
    )
